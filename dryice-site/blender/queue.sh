#!/bin/bash
# Полная очередь рендеров (CPU, ~1–1.5 ч на 4 ядрах)
cd "$(dirname "$0")"
for m in hero after before; do python3 render.py $m 2>&1 | grep -E "Saved|Error"; done
python3 render.py zones 2>&1 | grep -E "Saved|Error"
python3 render.py anim 0.75 60 2>&1 | grep -E "Saved|Error"
echo QUEUE_DONE
