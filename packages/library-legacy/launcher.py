#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EXE 启动器入口
双击或命令行运行，自动启动视频管理系统。
"""

import os
import sys

# 确保脚本所在目录为工作目录和 Python 路径
if getattr(sys, 'frozen', False):
    BASE_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
sys.path.insert(0, BASE_DIR)

# 导入 run.py 的 main
from run import main

if __name__ == "__main__":
    main()
