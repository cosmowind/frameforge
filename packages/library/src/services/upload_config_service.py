import os
import sys
import json
from config import *

_UPLOAD_OPTIONS_CACHE = None

def _load_upload_options() -> dict:
    """加载上传表单的枚举选项（国家、场景分类等）。
    数据来源: vendor-upload-pkg/stereo-upload-params/*.zh-CN.json
    """
    global _UPLOAD_OPTIONS_CACHE
    if _UPLOAD_OPTIONS_CACHE is not None:
        return _UPLOAD_OPTIONS_CACHE

    # 优先查找当前项目下的 vendor-upload-pkg，其次查找邻接目录
    params_dir = os.path.join(SRC_DIR, "vendor-upload-pkg", "stereo-upload-params")
    if not os.path.isdir(params_dir):
        # 邻接项目路径: ./vendor
        alt_dir = os.path.join(ROOT_DIR, "vendor-upload-pkg", "stereo-upload-params")
        if os.path.isdir(alt_dir):
            params_dir = alt_dir
    options = {
        "captureModes": [
            {"value": "single", "label": "单目"},
            {"value": "stereo", "label": "双目立体"},
            {"value": "three_views", "label": "三目"},
        ],
        "countries": [],
        "regions": {},
        "sceneCategories": [],
        "scenes": [],
        "gloves": [
            {"value": "No — bare hands", "label": "否 — 裸手"},
            {"value": "Yes — wearing gloves", "label": "是 — 佩戴手套"},
        ],
        "environments": [
            {"value": "Agriculture / Farming", "label": "农林"},
            {"value": "Construction / Trades", "label": "建筑/施工"},
            {"value": "Food Service / Dining", "label": "餐饮服务"},
            {"value": "Healthcare / Medical", "label": "医疗/健康"},
            {"value": "Home / Residential", "label": "住宅"},
            {"value": "Industrial Manufacturing", "label": "工业制造"},
            {"value": "Office / Knowledge Work", "label": "办公/知识工作"},
            {"value": "Other", "label": "其他"},
            {"value": "Outdoor / Nature", "label": "户外-自然"},
            {"value": "Outdoor / Urban", "label": "户外-城市"},
            {"value": "Retail / Commercial", "label": "零售/商业"},
            {"value": "Transportation", "label": "交通"},
            {"value": "Warehouse / Logistics", "label": "仓储物流"},
        ],
        "facilityVenues": [
            {"value": "Construction Site", "label": "施工现场"},
            {"value": "Hospital / Clinic", "label": "医院/诊所"},
            {"value": "Manufacturing Factory", "label": "制造工厂"},
            {"value": "Office Building", "label": "办公楼"},
            {"value": "Other", "label": "其他"},
            {"value": "Outdoor Site", "label": "户外场地"},
            {"value": "Residential Home", "label": "住宅"},
            {"value": "Restaurant / Kitchen", "label": "餐厅/厨房"},
            {"value": "Retail Store", "label": "零售商店"},
            {"value": "Warehouse", "label": "仓库"},
        ],
    }

    # 加载国家列表
    countries_path = os.path.join(params_dir, "countries.zh-CN.json")
    if os.path.isfile(countries_path):
        try:
            with open(countries_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for item in data.get("values", []):
                options["countries"].append({
                    "value": item["code"],
                    "label": item["label"].get("zh-CN", item["code"]),
                })
        except Exception as e:
            print(f"[warn] 加载国家列表失败: {e}", file=sys.stderr)

    # 加载地区列表（US/CN/JP/GB 结构化数据）
    regions_path = os.path.join(params_dir, "regions.zh-CN.json")
    if os.path.isfile(regions_path):
        try:
            with open(regions_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            for country_code, region_list in data.get("values", {}).items():
                options["regions"][country_code] = [
                    {
                        "value": r["value"],
                        "label": r.get("label", {}).get("zh-CN", r.get("value", "")),
                    }
                    for r in region_list
                ]
        except Exception as e:
            print(f"[warn] 加载地区列表失败: {e}", file=sys.stderr)

    # 加载场景分类（21 大类 + 子类）
    scene_path = os.path.join(params_dir, "scene-categories.zh-CN.json")
    if os.path.isfile(scene_path):
        try:
            with open(scene_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            scene_flat = []
            for cat in data.get("values", []):
                cat_zh = cat["label"].get("zh-CN", cat["id"])
                cat_en = cat["label"].get("en", cat["id"])
                entry = {
                    "value": cat["id"],
                    "label": cat_zh,
                    "subcategories": [],
                }
                for sub in cat.get("subcategories", []):
                    sub_id = sub["id"]
                    sub_zh = sub["label"].get("zh-CN", sub_id)
                    sub_en = sub["label"].get("en", sub_id)
                    entry["subcategories"].append({
                        "value": sub_id,
                        "label": sub_zh,
                    })
                    # flat scenes list: only subcategories (not top-level categories)
                    # display as "大类 · 子类中文-English" so users know the taxonomy
                    scene_flat.append({
                        "value": sub_id,
                        "label": f"{cat_zh} · {sub_zh}",
                        "labelEn": sub_en,
                        "categoryZh": cat_zh,
                        "categoryEn": cat_en,
                    })
                options["sceneCategories"].append(entry)
            # sort flat list by Chinese label alphabetically
            scene_flat.sort(key=lambda x: x["label"])
            options["scenes"] = scene_flat
        except Exception as e:
            print(f"[warn] 加载场景分类失败: {e}", file=sys.stderr)

    # 加载实时抓取的 Scene 名称列表（从上传页面下拉框提取的 809 个选项）
    scene_names_path = os.path.join(SRC_DIR, "tools", "scene_options_live.json")
    if os.path.isfile(scene_names_path):
        try:
            with open(scene_names_path, "r", encoding="utf-8") as f:
                live_scenes = json.load(f)
            options["sceneNames"] = [
                {
                    "value": s["value"],
                    "label": s["value"],
                    "labelZh": s.get("labelZh", s["value"]),
                }
                for s in live_scenes.get("scenes", [])
            ]
        except Exception as e:
            print(f"[warn] 加载实时场景名称失败: {e}", file=sys.stderr)
    else:
        options["sceneNames"] = []

    _UPLOAD_OPTIONS_CACHE = options
    return options



def get_upload_options():
    """返回上传表单的枚举选项数据（国家、场景分类等）"""
    return jsonify(_load_upload_options())



def get_upload_config():
    """Return current upload configuration"""
    return jsonify(UPLOAD_CONFIG)



def _load_upload_template_config():
    """Load upload template defaults from config.json."""
    # Implementation omitted for brevity
    return {}



def _save_upload_template_config(data: dict):
    """Save upload template defaults to config.json."""
    pass



