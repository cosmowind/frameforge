#!/usr/bin/env python3
"""
Fork of mcap_to_mp4.py: convert foxglove.CompressedVideo (H.265) in MCAP to MP4.
Single-camera (camera/0 only), one merged MP4 per session.
Usage: python mcap2mp4left.py <data0706_dir>
"""
import struct, sys, os, shutil, av
from fractions import Fraction

def rvarint(b,p):
    s=v=0
    while True:
        x=b[p];p+=1;v|=(x&0x7f)<<s
        if not(x&0x80):break
        s+=7
    return v,p
def flds(b):
    p=0;o=[]
    while p<len(b):
        k,p=rvarint(b,p);fn=k>>3;wt=k&7
        if wt==0:v,p=rvarint(b,p);o.append((fn,v))
        elif wt==2:ln,p=rvarint(b,p);o.append((fn,b[p:p+ln]));p+=ln
        elif wt==5:o.append((fn,b[p:p+4]));p+=4
        elif wt==1:o.append((fn,b[p:p+8]));p+=8
        else:break
    return o
def ts_ns(b):
    s=n=0
    for fn,v in flds(b):
        if fn==1:s=v
        if fn==2:n=v
    return s*10**9+n

def parse(path):
    data=open(path,'rb').read()
    assert data[:8]==b"\x89MCAP0\r\n"
    schemas={};channels={};frames={}
    def walk(buf):
        off=0
        while off+9<=len(buf):
            op=buf[off];length=struct.unpack_from('<Q',buf,off+1)[0];bs=off+9;be=bs+length
            if op not in range(1,16) or be>len(buf):
                return
            body=buf[bs:be]
            if op==3:
                sid=struct.unpack_from('<H',body,0)[0];p=2
                nl=struct.unpack_from('<I',body,p)[0];p+=4;nm=body[p:p+nl].decode();p+=nl
                schemas[sid]=nm
            elif op==4:
                cid=struct.unpack_from('<H',body,0)[0];p=2
                sid=struct.unpack_from('<H',body,p)[0];p+=2
                tl=struct.unpack_from('<I',body,p)[0];p+=4;tp=body[p:p+tl].decode()
                channels[cid]=(tp,schemas.get(sid,''))
            elif op==6:
                p=24+4;cl=struct.unpack_from('<I',body,p)[0];p+=4+cl
                rl=struct.unpack_from('<Q',body,p)[0];p+=8;walk(body[p:p+rl])
            elif op==5:
                cid,seq=struct.unpack_from('<HI',body,0);lt,pt=struct.unpack_from('<QQ',body,6)
                nm=channels.get(cid,('',''))[1]
                if nm=='foxglove.CompressedVideo':
                    its=None;d=b'';fmt=''
                    for fn,v in flds(body[22:]):
                        if fn==1 and isinstance(v,bytes):its=ts_ns(v)
                        elif fn==3:d=v
                        elif fn==4 and isinstance(v,bytes):fmt=v.decode('utf8','replace')
                    frames.setdefault(cid,[]).append((pt,(its if its is not None else pt),d,fmt))
            off=be
    walk(data[8:])
    return channels,frames

def process_session(session_dir, session_tag):
    """
    Find all mcap files in session_dir, extract camera/0 frames from each,
    sort globally by timestamp, and write one merged mp4.
    """
    mcap_files = sorted(
        [f for f in os.listdir(session_dir) if f.endswith('.mcap')],
        key=lambda x: int(x.replace('ego_','').replace('.mcap',''))
    )

    # Collect all camera/0 frames: (ts_ns, data)
    all_frames = []
    for mcap_file in mcap_files:
        path = os.path.join(session_dir, mcap_file)
        channels, frames = parse(path)

        for cid, fr in frames.items():
            topic = channels[cid][0]
            cam_num = topic.rstrip('/').split('/')[-1]
            if not cam_num.isdigit() or int(cam_num) != 0:
                continue
            for pt, ts, data, fmt in fr:
                all_frames.append((ts, data))

    if not all_frames:
        print(f"[{session_tag}] No camera/0 frames found")
        return

    # Sort by capture timestamp
    all_frames.sort(key=lambda x: x[0])

    # Write raw H.265 ES
    es_file = f'{session_tag}.es.h265'
    with open(es_file, 'wb') as f:
        for ts, data in all_frames:
            f.write(data)

    # Remux with correct PTS
    t0 = all_frames[0][0]
    TB = 90000
    inp = av.open(es_file)
    pkts = [p for p in inp.demux(inp.streams.video[0]) if p.size > 0]

    # Write to temp dir first to avoid OneDrive space issues
    temp_out = os.path.join(r'C:\temp_hmd', f'{session_tag}_merged.mp4')
    os.makedirs(r'C:\temp_hmd', exist_ok=True)

    out = av.open(temp_out, 'w')
    os_ = out.add_stream_from_template(inp.streams.video[0])
    os_.time_base = Fraction(1, TB)

    n = min(len(all_frames), len(pkts))
    for i in range(n):
        pk = pkts[i]
        pts = round((all_frames[i][0] - t0) / 1e9 * TB)
        pk.pts = pk.dts = pts
        pk.time_base = Fraction(1, TB)
        pk.stream = os_
        out.mux(pk)

    out.close()
    inp.close()
    os.remove(es_file)

    # Output to session_dir (not current working directory)
    final_out = os.path.join(session_dir, f'{session_tag}_merged.mp4')
    shutil.move(temp_out, final_out)

    # Clean up clip files in root directory for this session
    cwd = os.getcwd()
    for f in os.listdir(cwd):
        if f.startswith(session_tag + '_ego_') and f.endswith('_ego_camera_0.mp4'):
            try:
                os.remove(os.path.join(cwd, f))
            except:
                pass

    span = (all_frames[-1][0] - all_frames[0][0]) / 1e9
    print(f"[{session_tag}] {len(all_frames)} frames, {span:.2f}s -> {final_out}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python mcap2mp4left.py <data0706_dir>")
        sys.exit(1)

    root = sys.argv[1]
    sessions = sorted(
        [d for d in os.listdir(root)
         if os.path.isdir(os.path.join(root, d))
         and (d.startswith('session_') or d.startswith('0706-sample-session_'))],
        key=lambda x: int(x.split('_')[-1])
    )

    print(f"Found {len(sessions)} sessions in {root}")
    for sess in sessions:
        sess_dir = os.path.join(root, sess)
        if not any(f.endswith('.mcap') for f in os.listdir(sess_dir)):
            print(f"[{sess}] No mcap files found, skipping")
            continue
        process_session(sess_dir, sess)
    print("All done.")
