#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mcap2mp4_app  —  独立可执行工具（打包成 exe 后无任何外部依赖）

功能：
  1. 扫描输入文件夹 A 下的每个 session 子文件夹；
  2. 读取其中 session.json，把子文件夹重命名为  mmdd-deviceid-session-000xx
       - mmdd     : start_time_unix 的【本地时间】月日
       - deviceid : device_id 的后 6 位十六进制
       - 000xx    : session_name 里的编号（原样保留，如 00028）
  3. 把该 session 里所有 ego_*.mcap 的 camera/0（左相机）画面按时间戳合并，
     用 PyAV（内置 ffmpeg，无需系统 ffmpeg）转码/复用为一个 mp4，
     文件名与重命名后的文件夹同名：  mmdd-deviceid-session-000xx.mp4
  4. mp4 输出到用户指定的输出文件夹。

用法：
  mcap2mp4_app.exe <输入文件夹A> <输出文件夹>
  直接双击运行时，会交互式提示输入这两个路径。
"""
import os
import re
import sys
import json
import struct
import shutil
import tempfile
import datetime
import traceback
from fractions import Fraction

import av  # PyAV 自带 ffmpeg 库，打包后无需系统安装 ffmpeg

# 已经是目标格式的文件夹名（用于幂等重命名判断）
RENAMED_RE = re.compile(r'^\d{4}-[0-9a-fA-F]{6}-session-\d+$')


# --------------------------- MCAP 解析（容忍截断/损坏尾部） ---------------------------
def rvarint(b, p):
    s = v = 0
    while True:
        x = b[p]; p += 1; v |= (x & 0x7f) << s
        if not (x & 0x80):
            break
        s += 7
    return v, p


def flds(b):
    p = 0; o = []
    while p < len(b):
        k, p = rvarint(b, p); fn = k >> 3; wt = k & 7
        if wt == 0:
            v, p = rvarint(b, p); o.append((fn, v))
        elif wt == 2:
            ln, p = rvarint(b, p); o.append((fn, b[p:p + ln])); p += ln
        elif wt == 5:
            o.append((fn, b[p:p + 4])); p += 4
        elif wt == 1:
            o.append((fn, b[p:p + 8])); p += 8
        else:
            break
    return o


def ts_ns(b):
    s = n = 0
    for fn, v in flds(b):
        if fn == 1:
            s = v
        if fn == 2:
            n = v
    return s * 10 ** 9 + n


def parse(path):
    """返回 (channels, frames)。frames[cid] = [(pub_ns, capture_ns, data, fmt), ...]"""
    with open(path, 'rb') as f:
        data = f.read()
    assert data[:8] == b"\x89MCAP0\r\n", "不是有效的 MCAP 文件"
    schemas = {}; channels = {}; frames = {}

    def walk(buf):
        off = 0
        while off + 9 <= len(buf):
            op = buf[off]; length = struct.unpack_from('<Q', buf, off + 1)[0]
            bs = off + 9; be = bs + length
            if op not in range(1, 16) or be > len(buf):
                return  # 遇到截断/损坏，安全停止
            body = buf[bs:be]
            if op == 3:  # Schema
                sid = struct.unpack_from('<H', body, 0)[0]; p = 2
                nl = struct.unpack_from('<I', body, p)[0]; p += 4
                nm = body[p:p + nl].decode(); p += nl
                schemas[sid] = nm
            elif op == 4:  # Channel
                cid = struct.unpack_from('<H', body, 0)[0]; p = 2
                sid = struct.unpack_from('<H', body, p)[0]; p += 2
                tl = struct.unpack_from('<I', body, p)[0]; p += 4
                tp = body[p:p + tl].decode()
                channels[cid] = (tp, schemas.get(sid, ''))
            elif op == 6:  # Chunk
                p = 24 + 4
                cl = struct.unpack_from('<I', body, p)[0]; p += 4 + cl
                rl = struct.unpack_from('<Q', body, p)[0]; p += 8
                walk(body[p:p + rl])
            elif op == 5:  # Message
                cid, seq = struct.unpack_from('<HI', body, 0)
                lt, pt = struct.unpack_from('<QQ', body, 6)
                nm = channels.get(cid, ('', ''))[1]
                if nm == 'foxglove.CompressedVideo':
                    its = None; d = b''; fmt = ''
                    for fn, v in flds(body[22:]):
                        if fn == 1 and isinstance(v, bytes):
                            its = ts_ns(v)
                        elif fn == 3:
                            d = v
                        elif fn == 4 and isinstance(v, bytes):
                            fmt = v.decode('utf8', 'replace')
                    frames.setdefault(cid, []).append((pt, its if its is not None else pt, d, fmt))
            off = be

    walk(data[8:])
    return channels, frames


# --------------------------- 命名 ---------------------------
def compute_new_name(session_dir):
    """从 session.json 计算  mmdd-deviceid-session-000xx。失败返回 None。"""
    sj = os.path.join(session_dir, 'session.json')
    if not os.path.isfile(sj):
        return None
    try:
        with open(sj, 'r', encoding='utf-8') as f:
            info = json.load(f)
    except Exception:
        return None

    dev = str(info.get('device_id', '')).strip()
    last6 = dev[-6:] if len(dev) >= 6 else dev
    if not last6:
        return None

    t = info.get('start_time_unix')
    try:
        mmdd = datetime.datetime.fromtimestamp(float(t)).strftime('%m%d')
    except Exception:
        return None

    sess_name = str(info.get('session_name', '')).strip()
    m = re.search(r'(\d+)$', sess_name)
    num = m.group(1) if m else '00000'

    return f"{mmdd}-{last6}-session-{num}"


# --------------------------- 单个 session 处理 ---------------------------
def process_session(session_dir, out_dir, tmp_root):
    """合并该 session 内所有 ego_*.mcap 的 camera/0 帧 -> 一个 mp4。"""
    tag = os.path.basename(session_dir.rstrip('\\/'))

    mcap_files = sorted(
        [f for f in os.listdir(session_dir) if f.lower().endswith('.mcap')],
        key=lambda x: (len(x), x)  # ego_0000, ego_0001, ...
    )
    if not mcap_files:
        print(f"  [跳过] {tag}: 没有 .mcap 文件")
        return False

    # 收集所有 camera/0 帧：(capture_ns, data)
    all_frames = []
    for mf in mcap_files:
        path = os.path.join(session_dir, mf)
        try:
            channels, frames = parse(path)
        except Exception as e:
            print(f"  [警告] 解析失败 {mf}: {e}")
            continue
        for cid, fr in frames.items():
            topic = channels[cid][0]
            cam = topic.rstrip('/').split('/')[-1]
            if not cam.isdigit() or int(cam) != 0:
                continue
            for pt, ts, data, fmt in fr:
                if data:
                    all_frames.append((ts, data))

    if not all_frames:
        print(f"  [跳过] {tag}: 未找到 camera/0（左相机）画面")
        return False

    all_frames.sort(key=lambda x: x[0])

    # 写裸 H.265 ES 到临时目录
    es_file = os.path.join(tmp_root, f'{tag}.es.h265')
    with open(es_file, 'wb') as f:
        for ts, data in all_frames:
            f.write(data)

    t0 = all_frames[0][0]
    TB = 90000
    tmp_mp4 = os.path.join(tmp_root, f'{tag}.mp4')

    inp = av.open(es_file)
    try:
        pkts = [p for p in inp.demux(inp.streams.video[0]) if p.size > 0]
        out = av.open(tmp_mp4, 'w')
        try:
            # 兼容不同 PyAV 版本：新版(av>=?)用 add_stream_from_template；
            # 老版(如 Py3.8 上的 av 12)没有该方法，退回 add_stream(template=...)。
            tmpl = inp.streams.video[0]
            if hasattr(out, 'add_stream_from_template'):
                os_ = out.add_stream_from_template(tmpl)
            else:
                os_ = out.add_stream(template=tmpl)
            os_.time_base = Fraction(1, TB)
            n = min(len(all_frames), len(pkts))
            for i in range(n):
                pk = pkts[i]
                pts = round((all_frames[i][0] - t0) / 1e9 * TB)
                pk.pts = pk.dts = pts
                pk.time_base = Fraction(1, TB)
                pk.stream = os_
                out.mux(pk)
        finally:
            out.close()
    finally:
        inp.close()
        try:
            os.remove(es_file)
        except OSError:
            pass

    final_out = os.path.join(out_dir, f'{tag}.mp4')
    shutil.move(tmp_mp4, final_out)

    span = (all_frames[-1][0] - all_frames[0][0]) / 1e9
    fps = (len(all_frames) - 1) / span if span > 0 else 0
    print(f"  [完成] {tag}: {len(all_frames)} 帧, {span:.1f}s, {fps:.1f}fps -> {final_out}")
    return True


# --------------------------- 主流程 ---------------------------
def run(input_dir, out_dir):
    input_dir = os.path.abspath(input_dir)
    out_dir = os.path.abspath(out_dir)
    if not os.path.isdir(input_dir):
        print(f"错误：输入文件夹不存在: {input_dir}")
        return
    os.makedirs(out_dir, exist_ok=True)

    # 找出所有含 session.json 或 .mcap 的子文件夹
    subs = []
    for d in sorted(os.listdir(input_dir)):
        full = os.path.join(input_dir, d)
        if not os.path.isdir(full):
            continue
        has = os.path.isfile(os.path.join(full, 'session.json')) or \
            any(f.lower().endswith('.mcap') for f in os.listdir(full))
        if has:
            subs.append(d)

    if not subs:
        print(f"在 {input_dir} 下没有找到任何 session 文件夹。")
        return

    print(f"发现 {len(subs)} 个 session 文件夹。\n")
    tmp_root = tempfile.mkdtemp(prefix='mcap2mp4_')
    ok = fail = 0
    try:
        for d in subs:
            src = os.path.join(input_dir, d)
            # 1) 重命名文件夹
            if RENAMED_RE.match(d):
                new_dir = src  # 已是目标格式
                print(f"* {d} (已是目标格式)")
            else:
                new_name = compute_new_name(src)
                if not new_name:
                    print(f"* {d}: 无法读取 session.json，跳过重命名，仍尝试转码")
                    new_dir = src
                else:
                    new_dir = os.path.join(input_dir, new_name)
                    if os.path.abspath(new_dir) != os.path.abspath(src):
                        if os.path.exists(new_dir):
                            print(f"* {d} -> {new_name} (目标已存在，跳过重命名)")
                            new_dir = src
                        else:
                            os.rename(src, new_dir)
                            print(f"* {d} -> {new_name}")
                    else:
                        print(f"* {d} (名称无需改动)")
            # 2) 转码
            try:
                if process_session(new_dir, out_dir, tmp_root):
                    ok += 1
                else:
                    fail += 1
            except Exception as e:
                fail += 1
                print(f"  [错误] {os.path.basename(new_dir)}: {e}")
                traceback.print_exc()
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

    print(f"\n全部完成：成功 {ok} 个，失败/跳过 {fail} 个。")
    print(f"MP4 输出目录：{out_dir}")


def _init_console_utf8():
    """让打包后的 exe 在任意 Windows 控制台都能正确显示中文。"""
    if sys.platform == 'win32':
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
        except Exception:
            pass
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding='utf-8')
        except Exception:
            pass


def _ask(prompt):
    """安全地读一行输入：无控制台/EOF 时返回空串，绝不抛异常。"""
    try:
        return input(prompt).strip().strip('"').strip("'")
    except Exception:
        return ""


def main():
    try:
        _init_console_utf8()
    except Exception:
        pass

    args = [a for a in sys.argv[1:] if a and a.strip()]
    try:
        if len(args) >= 2:
            input_dir, out_dir = args[0], args[1]
        elif len(args) == 1:
            input_dir = args[0]
            out_dir = _ask("请输入【输出文件夹】路径（回车默认放到输入目录下的 _mp4）：\n> ") \
                or os.path.join(input_dir, '_mp4')
        else:
            print("=== mcap -> mp4 批量转换工具 ===\n")
            print("用法：把文件夹直接拖到 exe 上，或 mcap2mp4.exe <输入文件夹A> <输出文件夹>\n")
            input_dir = _ask("请输入【输入文件夹 A】（含多个 session 子文件夹）：\n> ")
            out_dir = _ask("请输入【输出文件夹】（mp4 存放位置，回车默认放到输入目录下的 _mp4）：\n> ") \
                or (os.path.join(input_dir, '_mp4') if input_dir else '')

        if not input_dir:
            print("未提供输入文件夹，退出。")
        else:
            run(input_dir, out_dir)
    except Exception as e:
        try:
            print(f"发生错误：{e}")
            traceback.print_exc()
        except Exception:
            pass

    # 双击运行时保持窗口，方便查看结果（无控制台也不会崩）
    if len(args) < 2:
        try:
            input("\n按回车键退出……")
        except Exception:
            pass


if __name__ == '__main__':
    main()
