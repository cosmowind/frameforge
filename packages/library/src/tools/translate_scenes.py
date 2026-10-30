"""
批量翻译 scene 名称为中文 (en→zh-CN)。
策略：先用内置词库 + 组合规则翻译，未命中的才走 Google Translate。
"""
import json, time, sys
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
INPUT_FILE = BASE / "tools" / "scene_options_live.json"

# ── 内置词库（优先使用，精确快速）──
WORD_MAP = {
    # 房间/空间
    "room": "房间", "area": "区域", "station": "台", "floor": "车间",
    "bay": "工位", "office": "办公室", "shop": "车间", "store": "仓库",
    "shed": "棚", "corner": "角落", "nook": "角落", "closet": "壁橱",
    "cabinet": "橱柜", "counter": "柜台", "desk": "桌", "table": "桌",
    "shelf": "货架", "aisle": "过道", "hallway": "走廊", "staircase": "楼梯",
    "balcony": "阳台", "patio": "露台", "porch": "门廊", "veranda": "走廊",
    "garden": "花园", "yard": "院子", "backyard": "后院", "greenhouse": "温室",
    "workshop": "车间", "warehouse": "仓库", "garage": "车库",
    "kitchen": "厨房", "bedroom": "卧室", "bathroom": "浴室", "living room": "客厅",
    "dining room": "餐厅", "laundry": "洗衣房", "utility room": "杂物间",
    "stockroom": "储藏室", "storeroom": "储藏室", "storage": "储藏室",
    "backroom": "后仓", "break room": "休息室", "waiting room": "等候室",
    "hotel room": "酒店房间", "sitting room": "起居室", "studio": "工作室",
    "study": "书房", "library": "图书馆", "gym": "健身房",
    "nursery": "苗圃", "toilet": "卫生间", "lounge": "休息室",
    "entryway": "玄关", "entrance": "入口", "stairwell": "楼梯间",
    "rooftop": "屋顶",
    # 功能区域
    "production": "生产", "processing": "加工", "packaging": "包装",
    "packing": "打包", "assembly": "组装", "fabrication": "制造",
    "repair": "维修", "sewing": "缝纫", "cutting": "裁剪", "stitching": "缝制",
    "ironing": "熨烫", "folding": "折叠", "sorting": "分拣", "mixing": "搅拌",
    "polishing": "抛光", "finishing": "精加工", "filling": "灌装",
    "decorating": "装饰", "arrangement": "整理", "testing": "检测",
    "quality control": "质检", "weighing": "称重", "wrapping": "包裹",
    "potting": "盆栽", "cleaning": "清洁", "washing": "清洗", "drying": "烘干",
    "staining": "染色", "alteration": "修改", "alterations": "修改",
    # 设施场所
    "bakery": "烘焙", "pastry": "糕点", "food": "食品", "snack": "零食",
    "canned goods": "罐头", "grocery": "杂货", "retail": "零售",
    "pharmacy": "药店", "prescription": "处方", "health": "保健",
    "beauty": "美妆", "souvenir": "纪念品", "tackle": "钓具",
    "hardware": "五金", "electrical": "电器", "craft": "手工",
    "floral": "花卉", "flower": "鲜花", "fragrance": "香水",
    "niche perfume": "小众香水", "toy": "玩具", "reel": "渔轮",
    "live bait": "活饵", "print": "印刷",
    # 工作位置
    "workbench": "工作台", "workstation": "工位", "work space": "工作区",
    "desk area": "办公区", "home office": "家庭办公室",
    "computer room": "电脑房", "electronics": "电子",
    # 服务场所
    "sales floor": "卖场", "display": "展示", "showroom": "展厅",
    "demonstration": "演示", "consultation": "咨询", "service": "服务",
    "checkout": "收银", "waiting": "等候", "reception": "接待",
    "concierge": "礼宾", "exhibition": "展览", "sample room": "样品间",
    # 外部
    "outdoor": "户外", "outdoors": "户外", "field": "田间",
    "garden bed": "花坛", "garden patch": "菜地", "garden walkway": "花园小径",
    "garden entrance": "花园入口", "garden centre": "园艺中心",
    "vegetable field": "菜地", "vegetable garden": "菜园",
    "outdoor seating": "户外座位", "outdoor plant": "户外植物",
    "outdoor alleyway": "户外巷道", "outdoor pavement": "户外人行道",
    "outdoor corner": "户外角落", "outdoor storage": "户外储藏",
    "roadside": "路边", "building": "建筑", "gate area": "大门区域",
    "house exterior": "房屋外部",
    # 住宅
    "home": "家", "residential": "住宅", "apartment": "公寓",
    "kids bedroom": "儿童卧室",
    # 其他
    "weight training": "力量训练", "recycling": "回收",
    "centre": "中心", "center": "中心",
    "machine": "机器", "line": "线", "sink": "水槽", "dish": "碗碟",
    "engine": "引擎", "parts": "零件", "material": "材料",
    "machine area": "机器区", "machine room": "机房",
    "packaging machine": "包装机", "packaging room": "包装间",
    "wooden": "木质", "woodworking": "木工", "textile": "纺织",
    "tailor": "裁缝", "tailoring": "裁缝",
    "shoe": "鞋", "cleaning area": "清洁区",
    "stain treatment": "污渍处理", "ribbon": "丝带",
    "gift": "礼品", "prep": "准备", "prep station": "准备台",
    "tiled": "瓷砖", "makeshift": "临时",
    "indoor": "室内", "outdoor": "户外",
    "common area": "公共区域", "entertainment area": "娱乐区",
    "play": "游戏", "crafting": "手工制作", "handcraft": "手工艺",
    "factory": "工厂", "factory floor": "工厂车间",
    "factory storage": "工厂仓库", "manufacturing": "制造",
    "industrial": "工业", "commercial": "商业",
    "circulation desk": "借阅台",
    "staff work area": "员工工作区",
    "customer service": "客服",
    "self service": "自助",
    "fitting": "试衣",
    "checkout counter": "收银台",
    "tools": "工具",
    "equipment": "设备",
    "design": "设计",
    "studio apartment": "单间公寓",
    "staff": "员工",
    "restaurant": "餐厅",
    "cafe": "咖啡厅",
    "lab": "实验室",
    "laboratory": "实验室",
    "clinic": "诊所",
    "hospital": "医院",
    "pharmacy counter": "药房柜台",
    "deli": "熟食",
    "butcher": "肉铺",
    "seafood": "海鲜",
    "produce": "农产品",
    "dairy": "乳制品",
    "frozen": "冷冻食品",
    "beverage": "饮料",
    "confectionery": "糖果",
}

def translate_compound(text):
    """用词库翻译复合词。返回 (zh_result, matched_count)"""
    words = text.strip()
    result = words  # fallback
    matched = 0

    # 1) 先精确匹配整句
    lower = words.lower().strip()
    if lower in WORD_MAP:
        return WORD_MAP[lower], 1

    # 2) 针对 "X / Y" 模式拆分
    if ";" in lower or "/" in lower:
        sep = ";" if ";" in lower else "/"
        parts = [p.strip() for p in lower.replace(sep, "|").split("|") if p.strip()]
        translated_parts = []
        for p in parts:
            t, m = translate_compound(p)
            translated_parts.append(t)
            matched += m
        return " / ".join(translated_parts), matched

    # 3) 尝试按空格分词翻译
    tokens = words.split()
    translated_tokens = []
    i = 0
    while i < len(tokens):
        # 尝试匹配 2-3 个连续词
        matched_phrase = None
        for n in range(min(3, len(tokens) - i), 0, -1):
            phrase = " ".join(tokens[i:i + n]).lower()
            if phrase in WORD_MAP:
                matched_phrase = WORD_MAP[phrase]
                matched += 1
                translated_tokens.append(matched_phrase)
                i += n
                break
        if matched_phrase is None:
            # 单词语法
            w = tokens[i].lower()
            if w in WORD_MAP:
                translated_tokens.append(WORD_MAP[w])
                matched += 1
            else:
                translated_tokens.append(tokens[i])
            i += 1

    return "".join(translated_tokens), matched

def translate_via_google(texts):
    """对未匹配词条使用 Google Translate 批量翻译"""
    from deep_translator import GoogleTranslator
    translator = GoogleTranslator(source="en", target="zh-CN")
    results = {}
    batch_size = 30
    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        print(f"\n  Google batch {i//batch_size + 1}: {len(batch)} items...")
        for text in batch:
            try:
                r = translator.translate(text)
                results[text] = r
                print(f"    {text[:40]:40s} → {r}")
            except Exception as e:
                print(f"    [ERR] {text[:40]:40s} → {e}")
                results[text] = text
            time.sleep(0.25)
        if i + batch_size < len(texts):
            time.sleep(2)
    return results

def main():
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    scenes = data["scenes"]  # list of strings
    total = len(scenes)
    print(f"Total: {total} scene names")

    # 第一步：词库匹配
    result = []  # list of {value, label, labelZh}
    unmatched = []
    matched_count = 0

    for s in scenes:
        zh, m = translate_compound(s)
        result.append({"value": s, "label": s, "labelZh": zh})
        if m > 0:
            matched_count += 1
        else:
            unmatched.append(s)

    print(f"\n词库命中: {matched_count}/{total}")
    print(f"需要 Google 翻译: {len(unmatched)}")

    # 第二步：Google 翻译未匹配项
    if unmatched:
        print(f"\n开始 Google 翻译 {len(unmatched)} 条...")
        gresults = translate_via_google(unmatched)

        # 更新结果
        for entry in result:
            if entry["value"] in gresults:
                entry["labelZh"] = gresults[entry["value"]]

    # 保存
    output = {"scenes": result, "count": total}
    with open(INPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\nSaved to {INPUT_FILE}")
    print("Done!")

if __name__ == "__main__":
    main()
