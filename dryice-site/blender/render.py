"""Рендер всех изображений для сайта.

    python3 render.py test            # быстрый черновик общего плана
    python3 render.py before|after|hero
    python3 render.py zones           # 4 макро-кадра зон
    python3 render.py anim            # кадры анимации очистки (для скролла)
Файлы пишутся в ../assets/ (PNG, конвертация в WebP/JPG — отдельным шагом).
"""
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine_scene as es  # noqa: E402

OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "raw"))
os.makedirs(OUT, exist_ok=True)

OVERVIEW = dict(loc=(0.05, -1.38, 1.08), target=(0.0, 0.05, 0.32), lens=34)


def render(path):
    bpy.context.scene.render.filepath = os.path.join(OUT, path)
    bpy.ops.render.render(write_still=True)


def main(mode, extra):
    es.build_engine_scene()
    s = bpy.context.scene
    scale = float(extra[0]) if extra else 1.0

    if mode in ("test", "before", "after", "hero"):
        cam = es.camera("Cam", OVERVIEW["loc"], OVERVIEW["target"], OVERVIEW["lens"],
                        fstop=5.6 if mode == "hero" else None)
        s.camera = cam
        if mode == "before":
            es.set_threshold(-5)
            es.build_fog("Dust", density=0.12, anim=False)
        elif mode == "after":
            es.set_threshold(5)
            es.build_fog(density=0.35, anim=False)
        elif mode == "hero":
            es.set_threshold(5)
            es.build_fog(density=0.32, anim=False)
            b = es.build_blaster()
            b.location = (0.36, -0.35, 0.86)
            b.rotation_euler = (math.radians(-28), math.radians(-22), 0)
        else:
            es.set_threshold(0.0)
            es.build_fog(density=0.6, anim=False)
        w, h = (1920, 1080) if mode != "test" else (960, 540)
        es.setup_render(int(w * scale), int(h * scale), samples=56 if mode != "test" else 24)
        render(f"{mode}.png")

    elif mode == "zones":
        es.set_threshold(5)
        es.build_fog(density=0.35, anim=False)
        shots = {
            "zone_block": ((-0.62, -0.55, 0.78), (-0.24, 0.0, 0.42), 55, 0.48),
            "zone_wiring": ((0.5, -0.28, 0.66), (0.17, 0.05, 0.47), 70, 0.42),
            "zone_turbo": ((0.88, -0.86, 0.6), (0.43, -0.44, 0.34), 60, 0.62),
            "zone_hoses": ((-0.1, -1.0, 0.62), (0.3, -0.58, 0.4), 50, 0.55),
        }
        only = extra[1:] if len(extra) > 1 else None
        es.setup_render(int(1600 * scale), int(1000 * scale), samples=56)
        for name, (loc, tgt, lens, focus) in shots.items():
            if only and name not in only:
                continue
            cam = es.camera(name, loc, tgt, lens, fstop=2.8, focus=focus)
            s.camera = cam
            render(f"{name}.png")

    elif mode == "anim":
        # статичная камера с лёгким наездом, волна очистки слева направо
        frames = int(extra[1]) if len(extra) > 1 else 72
        cam = es.camera("Cam", OVERVIEW["loc"], OVERVIEW["target"], OVERVIEW["lens"])
        s.camera = cam
        cam.keyframe_insert("location", frame=1)
        cam.location = Vector(OVERVIEW["loc"]) + Vector((0.0, 0.22, -0.18))
        cam.keyframe_insert("location", frame=frames)
        es.set_threshold(-0.95, frame=1)
        es.set_threshold(0.95, frame=frames)
        b = es.build_blaster()
        b.rotation_euler = (math.radians(-30), math.radians(-18), 0)
        for f, x in ((1, -0.82), (frames, 1.08)):
            b.location = (x, -0.3, 0.86)
            b.keyframe_insert("location", frame=f)
        fog = es.build_fog(density=0.3, anim=True)
        # туман «растёт» по мере очистки
        fog.scale = (0.2, 1.4, 0.45); fog.location = (-0.75, -0.1, 0.45)
        fog.keyframe_insert("scale", frame=1); fog.keyframe_insert("location", frame=1)
        fog.scale = (1.6, 1.4, 0.45); fog.location = (0.0, -0.1, 0.45)
        fog.keyframe_insert("scale", frame=frames); fog.keyframe_insert("location", frame=frames)
        for o in (cam, b, fog):
            ad = o.animation_data
            if ad and ad.action:
                for fc in getattr(ad.action, "fcurves", []):
                    for k in fc.keyframe_points:
                        k.interpolation = "LINEAR"
        s.frame_start, s.frame_end = 1, frames
        es.setup_render(int(1280 * scale), int(720 * scale), samples=22)
        start = int(extra[2]) if len(extra) > 2 else 1
        step = int(extra[3]) if len(extra) > 3 else 1
        os.makedirs(os.path.join(OUT, "seq"), exist_ok=True)
        for f in range(start, frames + 1, step):
            s.frame_set(f)
            render(os.path.join("seq", f"f{f:03d}.png"))

    elif mode == "save":
        es.set_threshold(0.0)
        es.build_fog(density=0.6)
        b = es.build_blaster()
        b.location = (0.36, -0.35, 0.86)
        s.camera = es.camera("Cam", OVERVIEW["loc"], OVERVIEW["target"], OVERVIEW["lens"])
        es.setup_render(1920, 1080)
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(os.path.dirname(__file__), "engine_bay.blend"))


if __name__ == "__main__":
    args = sys.argv[1:]
    main(args[0] if args else "test", args[1:])
