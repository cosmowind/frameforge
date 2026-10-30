import os
import json
import glob
import re
import shutil
from datetime import datetime
from typing import Optional, Dict, List, Any
from config import *


def _translate_with_minimax(chinese_text: str) -> str:
    """调用 MiniMax API 翻译中文→英文。失败返回空字符串。"""
    if not _MINIMAX_API_KEY:
        return ""
    if not chinese_text or not chinese_text.strip():
        return ""
    import json as _json
    try:
        payload = _json.dumps({
            "model": _MINIMAX_MODEL,
            "messages": [
                {"role": "system", "content": "You are a translator. Translate the user's Chinese text to English. Output ONLY the English translation, no explanations."},
                {"role": "user", "content": chinese_text}
            ],
            "temperature": 0.3
        }).encode("utf-8")
        import urllib.request
        req = urllib.request.Request(
            _MINIMAX_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {_MINIMAX_API_KEY}"
            }
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
        result = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if result and result.strip():
            return result.strip()
    except Exception as e:
        print(f"[translate] MiniMax API 失败: {e}", flush=True)
    return ""


