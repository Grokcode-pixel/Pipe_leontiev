"""Конвертирует PNG-рендеры из assets/raw в WebP/JPG для сайта.

    python3 export_assets.py
"""
import os
import glob
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "..", "assets", "raw")
IMG = os.path.join(HERE, "..", "assets", "img")
SEQ = os.path.join(HERE, "..", "assets", "seq")
os.makedirs(IMG, exist_ok=True)
os.makedirs(SEQ, exist_ok=True)

STILLS = {
    # имя: (макс. ширина, нужен ли JPG-фолбэк, прозрачность)
    "hero": (1920, True, False),
    "before": (1600, False, False),
    "after": (1600, False, False),
    "zone_block": (1400, False, False),
    "zone_wiring": (1400, False, False),
    "zone_turbo": (1400, False, False),
    "zone_hoses": (1400, False, False),
    "gun": (900, False, True),
    "nozzles": (900, False, True),
    "pellets": (1000, False, False),
}

for name, (maxw, jpg, alpha) in STILLS.items():
    src = os.path.join(RAW, f"{name}.png")
    if not os.path.exists(src):
        print("нет", name)
        continue
    im = Image.open(src)
    im = im.convert("RGBA" if alpha else "RGB")
    if im.width > maxw:
        im = im.resize((maxw, round(im.height * maxw / im.width)), Image.LANCZOS)
    im.save(os.path.join(IMG, f"{name}.webp"), "WEBP", quality=80, method=6)
    if jpg:
        im.convert("RGB").save(os.path.join(IMG, f"{name}.jpg"), "JPEG", quality=82, optimize=True, progressive=True)
    print("ok", name, im.size)

frames = sorted(glob.glob(os.path.join(RAW, "seq", "f*.png")))
for f in frames:
    im = Image.open(f).convert("RGB")
    im.save(os.path.join(SEQ, os.path.basename(f).replace(".png", ".webp")), "WEBP", quality=72, method=5)
print("кадров:", len(frames))
