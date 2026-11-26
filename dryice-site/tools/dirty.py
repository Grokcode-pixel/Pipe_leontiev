"""Делает кадр «до» из чистого фото: точно совпадает по ракурсу, поэтому подходит для слайдера.

    python3 dirty.py after.png before.png
Слои: масляный нагар в тёмных щелях, дорожная пыль на светлых плоскостях,
вертикальные потёки, тусклые блики и мелкие частицы.
"""
import sys

import numpy as np
from PIL import Image, ImageFilter

rng = np.random.default_rng(11)


def noise(h, w, cell, aniso=(1, 1)):
    gh, gw = max(2, int(h / cell / aniso[0]) + 2), max(2, int(w / cell / aniso[1]) + 2)
    g = Image.fromarray((rng.random((gh, gw)) * 255).astype(np.uint8))
    return np.asarray(g.resize((w, h), Image.BICUBIC), dtype=np.float32) / 255.0


def fbm(h, w, base, octaves=5, aniso=(1, 1)):
    acc, amp, tot = 0, 1.0, 0
    for o in range(octaves):
        acc = acc + noise(h, w, base / (2 ** o), aniso) * amp
        tot += amp
        amp *= 0.55
    return acc / tot


def smooth(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def main(src, dst):
    im = Image.open(src).convert("RGB")
    a = np.asarray(im, dtype=np.float32) / 255.0
    h, w, _ = a.shape
    lum = a @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    blur = np.asarray(Image.fromarray((lum * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(6)), dtype=np.float32) / 255
    cavity = np.clip((blur - lum) * 6, 0, 1)               # щели и края деталей
    edges = np.asarray(Image.fromarray((lum * 255).astype(np.uint8)).filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(2)), dtype=np.float32) / 255

    big = fbm(h, w, 220)
    mid = fbm(h, w, 60)
    fine = fbm(h, w, 8, 3)
    streak = fbm(h, w, 40, 4, aniso=(5, 0.6))              # вертикальные потёки

    # 1. пыльная плёнка по всему отсеку: тёмный пластик сереет и становится матовым
    film = 0.12 + 0.3 * smooth(big, 0.3, 0.8) + 0.28 * smooth(mid, 0.4, 0.75)
    film = film * (0.8 + 0.4 * fine)
    dust_col = np.array([0.36, 0.33, 0.28], dtype=np.float32)
    darkness = 1 - smooth(lum, 0.25, 0.75)                 # на светлой краске пыль почти не видна
    d = (film * (0.35 + 0.65 * darkness))[..., None]
    out = a * (1 - d) + dust_col * d

    # 2. масляный нагар: в щелях, у краёв деталей и пятнами
    oil = smooth(cavity * 1.3 + edges * 0.6 + mid * 0.55 + big * 0.25, 0.55, 1.05)
    oil = np.clip(oil + smooth(streak, 0.62, 0.82) * 0.5 * smooth(lum, 0.35, 0.8), 0, 1)
    oil *= 0.85 + 0.3 * fine
    oil_col = np.array([0.09, 0.07, 0.05], dtype=np.float32)
    o = np.clip(oil * 0.75, 0, 0.85)[..., None]
    out = out * (1 - o) + oil_col * o

    # 3. светлая краска: бурые разводы и потёки
    paint = smooth(lum, 0.55, 0.85)
    stain = paint * (0.25 + 0.45 * smooth(streak * 0.7 + big * 0.5, 0.45, 0.85))
    out = out * (1 - stain[..., None] * 0.55) + np.array([0.38, 0.31, 0.22]) * stain[..., None] * 0.55

    # 4. тусклые блики
    l2 = out @ np.array([0.2126, 0.7152, 0.0722], dtype=np.float32)
    hi = smooth(l2, 0.5, 1.0)[..., None]
    out = out * (1 - hi * 0.3) + out.mean(axis=2, keepdims=True) * 0.8 * hi * 0.3

    # 5. редкие крупинки
    specks = (rng.random((h, w)) > 0.9985).astype(np.float32)
    specks = np.asarray(Image.fromarray((specks * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.9)), dtype=np.float32) / 255
    out = out * (1 - specks[..., None] * 0.5) + np.array([0.08, 0.06, 0.04]) * specks[..., None] * 0.5

    grey = out.mean(axis=2, keepdims=True)
    out = out * 0.8 + grey * 0.2
    out = out * np.array([1.0, 0.97, 0.9]) * 0.95
    Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8)).save(dst)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
