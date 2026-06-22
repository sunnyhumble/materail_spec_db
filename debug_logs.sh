#!/bin/bash
# 调试模式：实时显示图片识别日志

echo "=== 材料规范数据库 - 图片识别调试模式 ==="
echo "按 Ctrl+C 退出"
echo ""

# 跟踪最新日志
sudo journalctl -u material-spec -f --no-pager --output=cat 2>&1 | while read line; do
    if echo "$line" | grep -qE "(Hybrid|OCR|LLM|性能|识别|test_values|specs|解析)"; then
        echo "[$(date '+%H:%M:%S')] $line"
    fi
done
