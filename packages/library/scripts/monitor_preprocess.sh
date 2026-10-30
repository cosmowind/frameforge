#!/bin/bash
# 监控 preprocess 进度（0701-0705 范围），每 5 分钟输出状态
LOG="/d/sp/dev/video-manager/runtime/logs/batch_preprocess_v5.log"
CACHE="/d/sp/dev/video-manager/runtime/hmd_cache"
BATCH_PID=27800
TOTAL=56
while true; do
  # 仅统计 2026-07-01/02/04 下的 mp4
  DONE=$(find "$CACHE/2026-07-01" "$CACHE/2026-07-02" "$CACHE/2026-07-04" -name "*.mp4" 2>/dev/null | wc -l)
  ELAPSED=$(ps -o etime= -p $BATCH_PID 2>/dev/null | tr -d ' ')
  CURRENT=$(grep -oE "\[stage1:[^]]+\] [0-9_]+_session_[0-9]+" "$LOG" 2>/dev/null | tail -1)
  echo "[$(date +%H:%M:%S)] 0701-0705: $DONE/$TOTAL  当前: $CURRENT  运行时长: $ELAPSED"
  if [ "$DONE" -ge "$TOTAL" ]; then
    echo "✅ 全部完成！"
    break
  fi
  # Git Bash 看不到 Windows 进程，用 tasklist 检查
  if ! tasklist //FI "PID eq $BATCH_PID" 2>/dev/null | grep -q "$BATCH_PID"; then
    echo "❌ 进程 $BATCH_PID 已退出"
    break
  fi
  sleep 300
done
