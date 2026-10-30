"""从 tasks.csv + environments.csv 生成 Sample Platform 任务清单 Excel"""
import csv
import re
import os
from collections import OrderedDict
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# ─── 0. 工序扩展（仅对原描述实在太简略的复杂任务做最小补充）────────
# 原则：简单/中等任务不扩展，保留原始描述。只对 hard 且原始＜3 步的关键任务略作补充。
PROCESS_EXPAND = {
    # 菜盆龙头 — 极简描述的适当补充
    '972e_d36a724f_b147_001':
        '取出菜盆进水脚，检查螺纹是否完好，将螺母旋入进水脚螺纹，放入垫片，用扳手拧紧加固',

    # 角阀 — 只有 easy 的"产品安装及打包"需要稍微补全
    '80fe_7fe2851d_5c36_001':
        '取出角阀放到工作台，将旋钮安上，放入螺丝，用电动螺丝刀转紧，放入塑料袋中',

    # 地漏 — 装箱打包 原描述太短
    '90e0_3580724f_2109_001':
        '将地漏装入包装盒，把包装盒叠好对齐，装入外箱码好',

    # 淋浴花洒 — 包装箱 原描述太短
    'cc80_d41e724f_5d2e_001':
        '折叠淋浴花洒的包装盒，放入泡沫内衬，将花洒放入盒中',

    # 淋浴龙头 — 组装按键把手 原描述太短
    '7cdc_3b7ca631_563a_001':
        '取出淋浴龙头主体，将钢琴按键对准安装槽位，用六角螺丝固定按键，取出侧开把手对准安装轴，拧紧把手螺丝',

    # 配件 — 零件组合 原描述太短
    'e64e_ffa8724f_e9b1_001':
        '取出塑料壳体检查接口，将铜管对准壳体接口，把塑料壳体和铜管拧到一起，检查连接是否牢固',

    # 合格证
    'worksh724f_45b5f5b8_3236_001':
        '将合格证取出，将绳子串入合格证中，拉绳对齐两端，打结固定',

    # 水龙头 — 密封圈
    'worksh724f_d55bf5b8_4a0a_001':
        '取出水龙头壳体，为水龙头装上密封圈放入槽中压实，再装上剩余零件，检查是否安装到位',

    # 水龙头 — 出水口
    'indust99c8_d55bf5b8_8192_001':
        '将出水口对准水龙头安装位，旋入出水口至底部，用塑料扳手旋紧加固',

    # 水龙头 — 清洁包装
    'worksh724f_d55b87ec_fd2c_001':
        '将水龙头擦拭干净，检查外观有无瑕疵，套袋并包装起来',

    # 眼镜 — 原描述太短
    'bd29_174b724f_fed7_001':
        '将眼镜拿起，检查镜片有无划痕，检查镜框是否变形，检查鼻托是否松动，确认后放回',

    # 金元宝 — 保持原风格
    '3b84_dd31724f_893d_001':
        '取纸对折压实，折角翻边压出边线，撑开纸面从内向外压平，捏出元宝造型整理成型',

    # 花蕊 — 花瓣组装
    'eace_37c21b30_51e3_001':
        '把橙色条缠绕在马克笔上绕若干圈，把橙色条按住形成一簇圆圈，整理花瓣形状，用线在花簇底部打结系紧',

    # 花蕊 — 组装花蕊
    'indust7088_91ed65b3_1640_001':
        '取短直棒捆紧橙色长条，用线固定橙色部分，把橙色接在绿色长条上，用线固定绿橙连接处，形成小花蕊',

    # 保洁
    '4ad1_6d87c01b_6672_001':
        '取出扫帚与畚斗，从区域一角开始逐块清扫，将灰尘垃圾集中成堆，用畚斗铲起垃圾倒入垃圾桶，收拾工具归位',
    '4ad1_3d49d57b_c046_001':
        '打湿抹布并拧干，到展厅逐个擦洗水龙头表面，擦拭桌面台面区域，清洁墙角积灰处，清洗抹布归位',
    '6ea0_00c8fdb6_b5c6_001':
        '用拖把拖地从一角开始，逐区域推进清洁不留死角，清扫垃圾集中到簸箕，把垃圾扫出办公室倒入垃圾桶',

    # 茶几
    '52cc_6ea0d57b_401f_001':
        '把茶具搬到清洗水槽，逐一冲洗茶杯茶壶内外，用抹布沾水擦洗茶桌台面，擦干水渍，将茶具逐个摆回原位',

    # 符纸
    '3224_2f56724f_15c7_001':
        '取出一叠符纸放上工作桌面，逐张拆分符纸避免撕裂，检查每张符纸有无破损，将完好的归拢对齐，用绳子扎捆打结系紧',

    # 泡沫槽
    '8511_0dca5c99_b2a1_001':
        '取出泡沫槽平放工作台，用小刀沿标记线划开泡沫表面，逐步加深切割至所需深度，掰开切断的泡沫块，清理碎屑，检查空间是否足够',

    # 鱼
    '80d4_36813fb4_0f08_001':
        '将鱼取出用水冲洗表面，放入砧板固定位置，用刮鳞刀从鱼尾向鱼头刮鳞，翻转鱼身刮另一面，检查鳞片是否刮净',

    # 成品
    'fec5_914c8538_937a_001':
        '给成品贴上标签，打包到箱子里，封上箱盖，用胶带封装加固',
}

# ─── 1. 读取数据 ───────────────────────────────────────────────
def read_csv(path):
    with open(path, 'r', encoding='utf-8-sig') as f:
        return list(csv.DictReader(f))

tasks = read_csv(r'runtime\data\tasks.csv')

# ─── 2. 工序描述 → 动作链解析 ──────────────────────────────────
def split_process(text):
    """将工序描述分割为独立动作短语"""
    if not text:
        return []
    text = re.sub(r'(然后|最后|接着|进而|同时|并且|之后|再)', r'︱\1', text)
    parts = re.split(r'[。，；、︱]', text)
    result = []
    for p in parts:
        p = p.strip().rstrip('。，；、').strip('。，；、 ')
        if p in ('然后', '最后', '接着', '进而', '同时', '并且', '之后', '再', '然', '最'):
            continue
        if len(p) >= 2:
            result.append(p)
    return result

def make_clean_tool(tool_str):
    if not tool_str or tool_str == '无':
        return ''
    t = tool_str.replace('，', '/').replace(',', '/').replace(' ', '')
    t = re.sub(r'/+', '/', t).strip('/')
    return t

def extract_action_phrase(phrase, max_len=10):
    """提取核心动作短语"""
    phrase = re.sub(r'^(将|把|给|对|往|用|向|从|在|按|然后|最后|接着|再|并|并且)', '', phrase).strip()
    phrase = re.sub(r'(了|着|过|的|地|得|等|后|时|处|中|吧|啊|呢|吗|哦|是否|是|否)$', '', phrase).strip()
    if len(phrase) > max_len:
        phrase = phrase[:max_len]
    return phrase if phrase else None

def parse_process(process, tool):
    parts = split_process(process)
    if not parts:
        return '操作', 1, '操作'

    short_actions = []
    full_actions = []
    seen = set()
    for p in parts:
        core = extract_action_phrase(p, max_len=8)
        full = extract_action_phrase(p, max_len=12)
        if core and core not in seen:
            short_actions.append(core)
            full_actions.append(full or core)
            seen.add(core)

    if not short_actions:
        return '操作', 1, '操作'

    action_count = len(short_actions)
    breakdown = '→'.join(short_actions[:12])
    
    clean_tool = make_clean_tool(tool)
    if clean_tool:
        chain = f'用{clean_tool}-' + '-'.join(full_actions[:12])
    else:
        chain = '-'.join(full_actions[:12])

    return breakdown, action_count, chain

# ─── 3. 难度映射 ───────────────────────────────────────────────
def diff_label(d):
    m = {'hard': '高', 'medium': '中', 'easy': '低'}
    return m.get((d or '').strip().lower(), '中')

# ─── 4. 环节（Stage）设计 ───────────────────────────────────────
# 简化 5 级流水线：备料→组装→检验→表面→终包
# 组合/重复任务不排环节

# 组合任务：任务工序 ≈ 另外两个独立任务的组合 → 跳过环节
_COMPOSITE_TASKS = {
    '972e_dffc55e0_ba5f_001',   # 菜盆龙头 装手柄擦拭 → 组装 + 表面
    'workshb30e_d55b17d2_5e98_001',  # 水龙头 配件安装并检验 → 组装 + 检验
    'worksh724f_d55b87ec_fd2c_001',  # 水龙头 清洁包装 → 表面 + 终包
    'd55b_56567931_b6c7_001',   # 水龙头 拆解维修 → 拆解 + 检修
    '90e0_aef9f4f8_e695_001',   # 地漏 拆箱检修 → 拆解 + 检修
    '90e0_39ba724f_e542_001',   # 地漏 全拆修 → 拆解 + 检修+组装+包装
    '90e0_35df724f_6902_001',   # 地漏 检修 → 实际为 组装+装袋 组合
    '7cdc_ecd6ffd0_93c1_001',   # 淋浴龙头 擦拭装袋 → 表面 + 终包
    'cc80_d41e724f_5d2e_001',   # 淋浴花洒 包装箱 → 组装 + 终包
    '80fe_54cc724f_1139_001',   # 角阀 贴标装袋 → 贴标 + 装袋
    '80fe_25bb724f_cc76_001',   # 角阀 成品组装与装箱 → 成品组装 + 装箱
    '80fe_6c1d724f_cc76_001',   # 角阀 成品全组装 → 与成品全组装2+装箱 组合
}


def _get_stage_num(tn, pr):
    """只用任务名判断，返回简化流水线阶段 1-5"""
    # 1: 备料 / 拆解
    if any(k in tn for k in ['取配件', '整合配件', '拆解', '拆箱', '全拆',
                             '切割', '拆分', '预处理', '刮鳞']):
        return 1

    # 2: 组装 / 安装
    if any(k in tn for k in ['装主体', '装机', '安装底座', '固定入水孔', '食品生产',
                             '阀芯', '密封圈', '入水口', '进水脚', '固定脚',
                             '装入水口', '铜管', '软管', '出水口', '弯管', '水嘴', '分水口',
                             '壳体组装', '装配件', '配件安装', '配件组装', '配件组成', '零件组合',
                             '手柄', '把手', '旋钮', '按键', '组装按键',
                             '圆弧壳', '保护壳', '冷热', '产品打标', '上螺丝',
                             '装配装箱']):
        return 2

    # 3: 检验 / 测试
    if any(k in tn for k in ['试水', '检查产品', '检验']):
        return 3
    if '检修' in tn:
        return 3

    # 4: 表面处理
    if any(k in tn for k in ['擦拭', '清洁', '打蜡', '清洗', '拖地', '打扫', '擦洗']):
        return 4

    # 5: 终包
    if any(k in tn for k in ['贴标', '装袋', '合格证', '摆放',
                             '打包', '装箱', '装盒', '包装',
                             '成品装盒', '产品装箱', '产品打包', '成品组装', '成品全组装',
                             '装盒入箱', '折纸', '装袋叠箱', '加固折叠',
                             '产品安装及打包']):
        return 5

    return 3  # fallback


def should_skip_stage(t, kept_first_tids):
    """判断任务是否跳过环节编号"""
    tid = t.get('task_id', '').strip()
    tn = t.get('task', '')

    # 1. 组合任务
    if tid in _COMPOSITE_TASKS:
        return True

    # 2. 同名重复：只保留第一个（按 kept_first_tids 中的 task_id）
    if tn in kept_first_tids and tid != kept_first_tids[tn]:
        return True

    return False


# ─── 5. 场景分配 ───────────────────────────────────────────────
# 卫浴生产厂系列：菜盆龙头 → 成品 + 合格证 + 泡沫槽
# 其他按实际场景分配
_PRODUCT_SCENE = {
    '菜盆龙头': '卫浴生产厂', '洗面盆龙头': '卫浴生产厂', '水龙头': '卫浴生产厂',
    '角阀': '卫浴生产厂', '淋浴龙头': '卫浴生产厂', '淋浴花洒': '卫浴生产厂',
    '地漏': '卫浴生产厂', '小水龙头': '卫浴生产厂', '手柄': '卫浴生产厂',
    '弯管': '卫浴生产厂', '铜管': '卫浴生产厂', '成品': '卫浴生产厂',
    '合格证': '卫浴生产厂', '泡沫槽': '卫浴生产厂',
    '保洁': '办公室',
    '电脑': '电脑店',
    '符纸': '手工作坊',
    '花蕊': '手工作坊',
    '眼镜': '眼镜店',
    '鱼': '鱼市',
    '粽子': '厨房',
    '金元宝': '手工作坊',
    '茶几': '茶室',
}

# ─── 6. 环境标签（保留用于环境说明 sheet）─────────────────────
_ENV_LABELS = {
    'env_42fd3fbeab': '组装工作台',
    'env_65ce4e1671': '泡沫槽简易工作区',
    'env_7c045f15db': '打标机工作区',
    'env_87d59f6bc3': '试水台',
    'env_89a3dacc6a': '泡沫槽塑料箱工作区',
    'env_b3894b5b71': '手工品工作台',
    'env_shishuitai': '试水台',
    'env_huasa': '花洒组装区',
    'env_chejian': '车间空地平台',
    'env_office': '办公室',
    'env_wash': '清洗水槽',
    'env_mechine': '角阀加固机器',
    'env_zongzi': '食品制作区',
    'env_fuzhi': '符纸仓库',
    'env_changzhuo': '物品堆放长桌',
    'env_zhanting': '产品展厅',
    'env_keting': '接待客厅',
    'env_linyu': '淋浴固定电机',
    'env_huojia': '仓库货架区',
}

envs_list = read_csv(r'runtime\data\environments.csv')
env_sheet_data = []
for env in envs_list:
    env_id = env.get('env_id', '').strip()
    label = _ENV_LABELS.get(env_id, env.get('environment', '未知环境'))
    desc = env.get('environment_description', '').strip()
    desc_en = env.get('environment_description_en', '').strip()
    facility = env.get('facility_venue', '').strip()
    location = env.get('location_address', '').strip()
    parts = [f'中文: {desc}']
    if desc_en:
        parts.append(f'英文: {desc_en}')
    if location:
        parts.append(f'位置: {location}')
    if facility:
        parts.append(f'场景: {facility}')
    full_desc = '\n'.join(parts) if desc else '—'
    env_sheet_data.append((env_id, label, full_desc))

def get_env_short(t):
    env_desc = t.get('environment_description', '').strip()
    if env_desc:
        short = env_desc.split('，')[0].split(',')[0].strip()
        return short[:15] if len(short) > 15 else short
    return '—'

# ─── 7. 产品分组 ───────────────────────────────────────────────
product_merge = {
    '花洒': '淋浴花洒', '花洒配件1': '淋浴花洒', '花洒箱子': '淋浴花洒',
    '淋浴主体': '淋浴花洒',
    '角阀配件': '角阀', '壳体配件': '角阀', '水嘴配件': '角阀', '配件': '角阀',
    '清洁': '保洁',
    '出水口': '水龙头',
}

product_order = [
    '菜盆龙头', '洗面盆龙头', '水龙头', '角阀', '淋浴龙头', '淋浴花洒',
    '地漏', '小水龙头', '手柄', '弯管', '铜管',
    '成品', '保洁', '电脑', '符纸', '花蕊', '眼镜', '鱼', '粽子', '金元宝', '泡沫槽', '茶几',
]

grouped = OrderedDict()
for p in product_order:
    grouped[p] = []

for t in tasks:
    product = t.get('product', '').strip()
    if not product:
        continue
    product = product_merge.get(product, product)
    if product not in grouped:
        grouped[product] = []
    grouped[product].append(t)


def task_sort_key(t, is_skipped=False):
    """按阶段类别排序，跳过的排在同类别末尾"""
    tn = t.get('task', '')
    pr = t.get('process', '')
    cat = _get_stage_num(tn, pr)
    # 跳过的排在同类末尾
    return (cat, 1 if is_skipped else 0, tn)


# ─── 8. 构建数据行 ─────────────────────────────────────────────
class TaskRow:
    def __init__(self, seq, scene, product, task_name,
                 stage, diff, action_count, breakdown, chain, note):
        self.seq = seq; self.scene = scene; self.product = product
        self.task_name = task_name; self.stage = stage
        self.diff = diff; self.action_count = action_count
        self.breakdown = breakdown; self.chain = chain; self.note = note

rows = []
seq = 0

for product, task_list in grouped.items():
    if not task_list:
        continue

    # 找出每个 task_name 的"第一个" task_id（保留环节）
    from collections import OrderedDict as OD
    first_tids = {}
    for t in task_list:
        tn = t.get('task', '')
        tid = t.get('task_id', '').strip()
        if tn not in first_tids:
            first_tids[tn] = tid

    # 标记每个任务是否 skip
    task_flags = []
    for t in task_list:
        skipped = should_skip_stage(t, first_tids)
        task_flags.append((t, skipped))

    # 排序：非 skip 的按阶段排前面，skip 的放后面
    task_flags.sort(key=lambda x: task_sort_key(x[0], x[1]))

    # 计算 kept 任务用到了哪些阶段编号（紧凑映射）
    kept = [x for x in task_flags if not x[1]]
    skip_list = [x for x in task_flags if x[1]]

    if kept:
        # 收集所有出现过的原始阶段编号并排序
        used_stages = sorted(set(
            _get_stage_num(t.get('task', ''), t.get('process', '')) for t, _ in kept
        ))
        stage_map = {orig: i + 1 for i, orig in enumerate(used_stages)}
        total_stages = len(used_stages)
    else:
        used_stages = []
        stage_map = {}
        total_stages = 0

    # 给每个任务映射环节标签（用 dict 而不是对象属性）
    stage_label_map = {}  # task_id → stage_label
    for t, _ in kept:
        tid = t.get('task_id', '').strip()
        orig = _get_stage_num(t.get('task', ''), t.get('process', ''))
        mapped = stage_map.get(orig, 1)
        stage_label_map[tid] = f'{mapped}/{total_stages}' if total_stages > 0 else '—'
    for t, _ in skip_list:
        tid = t.get('task_id', '').strip()
        stage_label_map[tid] = '—'

    # 按排序顺序输出全部
    for t, _ in kept + skip_list:
        seq += 1
        task_id = t.get('task_id', '').strip()

        # 应用工序扩展（仅受影响的少数任务）
        process_orig = t.get('process', '')
        process = PROCESS_EXPAND.get(task_id, process_orig)

        tool = t.get('tool', '').strip()
        diff = diff_label(t.get('difficulty', ''))
        task_name = t.get('task', '').strip()
        breakdown, count, chain = parse_process(process, tool)

        scene = _PRODUCT_SCENE.get(product, '其他')
        stage = stage_label_map.get(task_id, '—')

        # 说明
        notes = []
        if t.get('quota_min', '').strip():
            notes.append(f'配额{t.get("quota_min").strip()}s')
        note = '；'.join(notes) if notes else '—'

        rows.append(TaskRow(
            seq=seq, scene=scene, product=product, task_name=task_name,
            stage=stage, diff=diff, action_count=count,
            breakdown=breakdown, chain=chain, note=note
        ))

# ─── 8. 写 Excel ───────────────────────────────────────────────
wb = Workbook()

# ===== Sheet 1: 任务清单 =====
ws = wb.active
ws.title = 'Sample Platform 任务清单'

hff_font = Font(name='Arial', size=11, bold=True, color='FFFFFF')
hff_fill = PatternFill('solid', fgColor='2F5496')
hff_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
body_font = Font(name='Arial', size=10)
l_align = Alignment(horizontal='left', vertical='center', wrap_text=True)
c_align = Alignment(horizontal='center', vertical='center', wrap_text=True)
border = Border(
    left=Side(style='thin'), right=Side(style='thin'),
    top=Side(style='thin'), bottom=Side(style='thin')
)
diff_fills = {
    '高': PatternFill('solid', fgColor='FFC7CE'),
    '中': PatternFill('solid', fgColor='FFEB9C'),
    '低': PatternFill('solid', fgColor='C6EFCE'),
}
alt_fills = [
    PatternFill('solid', fgColor='FFFFFF'),
    PatternFill('solid', fgColor='F2F2F2'),
]

headers = ['序号', '场景', '产品类别', '任务工序', '环节', '难度',
           '动作数', '动作拆解', '工序链(工具-动作)', '说明']
widths = [6, 12, 14, 20, 7, 6, 7, 34, 52, 16]

for c, (h, w) in enumerate(zip(headers, widths), 1):
    cell = ws.cell(row=1, column=c, value=h)
    cell.font = hff_font; cell.fill = hff_fill
    cell.alignment = hff_align; cell.border = border
    ws.column_dimensions[get_column_letter(c)].width = w

cur_product = ''
fill_idx = 0
product_ranges = OrderedDict()

for i, r in enumerate(rows):
    rn = i + 2

    if r.product != cur_product:
        cur_product = r.product
        fill_idx += 1
        product_ranges[cur_product] = [rn, rn]
    else:
        product_ranges[cur_product][1] = rn

    row_fill = alt_fills[fill_idx % 2]

    vals = [r.seq, r.scene, r.product, r.task_name, r.stage,
            r.diff, r.action_count, r.breakdown, r.chain, r.note]

    for c, v in enumerate(vals, 1):
        cell = ws.cell(row=rn, column=c, value=v)
        cell.font = body_font; cell.border = border
        cell.fill = row_fill

        if c in (1, 2, 3, 4, 5, 6, 7):
            cell.alignment = c_align
        else:
            cell.alignment = l_align

        if c == 6 and v in diff_fills:
            cell.fill = diff_fills[v]

# 合并产品列 & 场景列
for prod, (sr, er) in product_ranges.items():
    if sr < er:
        ws.merge_cells(start_row=sr, start_column=3, end_row=er, end_column=3)
        ws.merge_cells(start_row=sr, start_column=2, end_row=er, end_column=2)

ws.freeze_panes = 'A2'
ws.auto_filter.ref = f'A1:{get_column_letter(len(headers))}{len(rows)+1}'
ws.row_dimensions[1].height = 30
for rw in range(2, len(rows)+2):
    ws.row_dimensions[rw].height = 28

# ===== Sheet 2: 环境说明 =====
ws2 = wb.create_sheet('环境说明')

env_hff_font = Font(name='Arial', size=11, bold=True, color='FFFFFF')
env_hff_fill = PatternFill('solid', fgColor='4472C4')
env_hff_align = Alignment(horizontal='center', vertical='center', wrap_text=True)

env_headers = ['序号', '环境编号', '环境简标', '环境详细描述']
env_widths = [6, 18, 20, 70]

for c, (h, w) in enumerate(zip(env_headers, env_widths), 1):
    cell = ws2.cell(row=1, column=c, value=h)
    cell.font = env_hff_font; cell.fill = env_hff_fill
    cell.alignment = env_hff_align; cell.border = border
    ws2.column_dimensions[get_column_letter(c)].width = w

for idx, (env_id, label, desc) in enumerate(env_sheet_data):
    vals = [idx+1, env_id, label, desc]
    for c, v in enumerate(vals, 1):
        cell = ws2.cell(row=idx+2, column=c, value=v)
        cell.font = body_font; cell.border = border
        cell.alignment = l_align if c == 4 else c_align
    ws2.row_dimensions[idx+2].height = 55

ws2.freeze_panes = 'A2'
ws2.row_dimensions[1].height = 28

# ─── 保存 ─────────────────────────────────────────────────────
out = r'docs\汇报情况\Sample_AI任务清单_20260630.xlsx'
os.makedirs(os.path.dirname(out), exist_ok=True)
wb.save(out)
print(f'已生成: {out}')
print(f'共 {len(rows)} 个任务，{len(product_ranges)} 个产品类别')
print(f'环境说明共 {len(env_sheet_data)} 条')

# 打印摘要（含环节）
print(f'\n{"产品":<16} {"总任务":>4}  {"有环节":>4}  {"跳过":>3}  {"环节范围":>10}')
print('-' * 52)
for prod, (sr, er) in product_ranges.items():
    prod_rows = rows[sr-2:er-1]  # sr is 1-based row index
    staged = [r for r in prod_rows if r.stage != '—']
    skipped = [r for r in prod_rows if r.stage == '—']
    first_s = staged[0].stage if staged else '—'
    last_s = staged[-1].stage if staged else '—'
    print(f'{prod:<16} {len(prod_rows):>4}  {len(staged):>4}  {len(skipped):>3}  {first_s} ~ {last_s}')
