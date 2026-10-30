import os
import json
import glob
import re
import shutil
from datetime import datetime
from typing import Optional, Dict, List, Any
from config import *


def _startup_auto_warm():
    """Background thread: after Flask starts, auto-queue pending items from CSV.

    Waits a few seconds for Flask to finish initializing, then reads the CSV
    and calls _auto_warm_all().  This ensures that after a restart, pending
    items are automatically picked up without requiring a re-scan.
    """
    import time
    # Wait for Flask to finish loading routes etc.
    time.sleep(3)
    try:
        rows = read_csv()
        if rows:
            print(f"[startup auto-warm] Found {len(rows)} rows in CSV, checking pending items...", file=sys.stderr)
            _auto_warm_all(rows)
    except Exception as e:
        print(f"[startup auto-warm failed] {e}", file=sys.stderr)


# Kick off startup auto-warm (in a daemon thread, so it doesn't block import/startup).
# In Flask debug mode (Werkzeug reloader), the module is loaded twice.
# We use a file-based flag to ensure the warm-up only runs once per startup.
# Controlled by env var AUTO_PREPROCESS_ENABLED (set by run.py after disk space check).
import atexit
if os.environ.get("AUTO_PREPROCESS_ENABLED") == "1":
    if not os.path.isfile(_startup_warm_flag):
        try:
            with open(_startup_warm_flag, "w") as _f:
                _f.write("1")
        except Exception:
            pass
        threading.Thread(target=_startup_auto_warm, daemon=True).start()
else:
    print("[startup] 自动预处理已禁用（磁盘空间不足或用户选择跳过）", file=sys.stderr)

