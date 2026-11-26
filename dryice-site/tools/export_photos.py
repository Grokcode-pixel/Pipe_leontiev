"""Готовит фото для сайта.

    python3 tools/export_photos.py

1. Из чистого кадра assets/photo_raw/after.png делает «до» (tools/dirty.py) —
   тот же ракурс, поэтому слайдер и анимация совпадают до пикселя.
2. Конвертирует assets/photo_raw/*.png в WebP (и hero ещё в JPG для соцсетей) в assets/img/.
"""
import os
import sys

from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import dirty  # noqa: E402

RAW = os.path.join(HERE, "..", "assets", "photo_raw")
IMG = os.path.join(HERE, "..", "assets", "img")
os.makedirs(IMG, exist_ok=True)

dirty.main(os.path.join(RAW, "after.png"), os.path.join(RAW, "before.png"))

for f in sorted(os.listdir(RAW)):
    if not f.endswith(".png"):
        continue
    name = f[:-4]
    im = Image.open(os.path.join(RAW, f)).convert("RGB")
    im.save(os.path.join(IMG, f"{name}.webp"), "WEBP", quality=82, method=6)
    if name == "hero":
        im.save(os.path.join(IMG, "hero.jpg"), "JPEG", quality=84, optimize=True, progressive=True)
    print("ok", name, im.size)
