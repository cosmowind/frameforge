"""
上传选项加载服务。
从 vendor-upload-pkg/stereo-upload-params/*.zh-CN.json 加载表单枚举选项。
"""

import json
import os

from config import SRC_DIR, ROOT_DIR

_UPLOAD_OPTIONS_CACHE = None


def load_upload_options():
    """加载上传表单的枚举选项（国家、场景分类等）。"""
    global _UPLOAD_OPTIONS_CACHE
    if _UPLOAD_OPTIONS_CACHE is not None:
        return _UPLOAD_OPTIONS_CACHE

    params_dir = os.path.join(SRC_DIR, "vendor-upload-pkg", "stereo-upload-params")
    if not os.path.isdir(params_dir):
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
            {"value": "Retail and Consumer Goods", "label": "Retail and Consumer Goods - 零售和消费品"},
            {"value": "Fashion", "label": "Fashion - 时尚"},
            {"value": "Repair Services", "label": "Repair Services - 维修服务"},
            {"value": "Food and Beverage", "label": "Food and Beverage - 餐饮"},
            {"value": "Home", "label": "Home - 住宅 ⚠️已满，请勿选择"},
            {"value": "Construction and Hardware", "label": "Construction and Hardware - 建筑和五金"},
            {"value": "Food Processing", "label": "Food Processing - 食品加工"},
            {"value": "Printing and Design", "label": "Printing and Design - 印刷和设计"},
            {"value": "Factory", "label": "Factory - 工厂 ⚠️已满，请勿选择"},
            {"value": "Hospitality", "label": "Hospitality - 酒店餐饮"},
            {"value": "Automotive and Transport", "label": "Automotive and Transport - 汽车和运输"},
            {"value": "Sports and Recreation", "label": "Sports and Recreation - 运动和休闲"},
            {"value": "Creative Workshops", "label": "Creative Workshops - 创意工坊"},
            {"value": "Administrative", "label": "Administrative - 行政 ⚠️已满，请勿选择"},
            {"value": "Education and Training", "label": "Education and Training - 教育和培训"},
            {"value": "Industrial Manufacturing", "label": "Industrial Manufacturing - 工业制造"},
            {"value": "Energy and Utilities", "label": "Energy and Utilities - 能源和公用事业"},
            {"value": "Healthcare and Pharmacy", "label": "Healthcare and Pharmacy - 医疗和药房"},
            {"value": "Administrative & Office Services", "label": "Administrative & Office Services - 行政和办公服务 ⚠️已满，请勿选择"},
            {"value": "Cleaning and Sanitation", "label": "Cleaning and Sanitation - 清洁和卫生"},
            {"value": "Laboratory / Scientific", "label": "Laboratory / Scientific - 实验室/科研"},
            {"value": "Childcare and Caregiving", "label": "Childcare and Caregiving - 育儿和护理"},
            {"value": "Public Safety and Emergency Response", "label": "Public Safety and Emergency Response - 公共安全和应急响应"},
            {"value": "Agriculture and Farming", "label": "Agriculture and Farming - 农业"},
            {"value": "Beauty and Personal Care", "label": "Beauty and Personal Care - 美容和个人护理"},
            {"value": "Entertainment and Events", "label": "Entertainment and Events - 娱乐和活动"},
            {"value": "Other", "label": "Other - 其他"},
        ],
        "facilityVenues": [
            {"value": "Construction Site", "label": "施工现场"},
            {"value": "Hospital / Clinic", "label": "医院/诊所"},
            {"value": "Manufacturing Factory", "label": "制造工厂"},
            {"value": "Office Building", "label": "办公楼"},
            {"value": "Other", "label": "其他"},
            {"value": "Outdoor Field", "label": "户外场地"},
            {"value": "Restaurant / Café", "label": "餐厅/咖啡馆"},
            {"value": "Retail Store", "label": "零售商店"},
            {"value": "School / University", "label": "学校/大学"},
            {"value": "Transportation Hub", "label": "交通枢纽"},
            {"value": "Warehouse", "label": "仓库"},
            {"value": "Workshop / Garage", "label": "工作室/车库"},
        ],
    }

    # 从 JSON 文件加载国家/地区/场景
    for key, filename in [("countries", "countries.zh-CN.json"),
                           ("regions", "regions.zh-CN.json"),
                           ("sceneCategories", "scene_categories.zh-CN.json"),
                           ("scenes", "scenes.zh-CN.json")]:
        filepath = os.path.join(params_dir, filename)
        if os.path.isfile(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if key == "regions":
                    options[key] = {c: v for c, v in (data if isinstance(data, dict) else {}).items()}
                else:
                    options[key] = data if isinstance(data, list) else []
            except Exception:
                pass

    _UPLOAD_OPTIONS_CACHE = options
    return options
