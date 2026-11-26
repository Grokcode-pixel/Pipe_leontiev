"""Оборудование: криопистолет, сменные сопла, гранулы CO2.

    python3 equipment.py gun|nozzles|pellets [scale]
"""
import math
import os
import random
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engine_scene as es  # noqa: E402
from engine_scene import M, box, cyl, torus, tube  # noqa: E402

OUT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "assets", "raw"))
os.makedirs(OUT, exist_ok=True)


def studio(rim_energy=300, key=90):
    w = bpy.data.worlds.new("W")
    bpy.context.scene.world = w
    w.node_tree.nodes["Background"].inputs["Color"].default_value = (0.004, 0.005, 0.007, 1)

    def area(name, loc, target, size, energy, color, sy=None):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy, ld.color, ld.size = energy, color, size
        ld.shape = "RECTANGLE"
        ld.size_y = sy or size
        o = bpy.data.objects.new(name, ld)
        bpy.context.scene.collection.objects.link(o)
        o.location = loc
        o.rotation_euler = (Vector(target) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()

    area("Key", (0.4, -0.9, 1.0), (0, 0, 0), 0.9, key, (1, 0.97, 0.94))
    area("Rim", (-0.6, 0.9, 0.6), (0, 0, 0), 1.2, rim_energy, (0.1, 0.85, 1.0), sy=0.2)
    area("Top", (0, 0, 1.4), (0, 0, 0), 0.4, 60, (0.8, 0.95, 1.0), sy=1.4)
    area("Strip", (1.0, 0.3, 0.4), (0, 0, 0.1), 0.08, 80, (1, 1, 1), sy=1.0)


def mats():
    es.materials()
    for k in list(M):
        pass
    es.set_threshold(9)  # всё чистое
    M["graphite"] = es.mat("Graphite", (0.018, 0.02, 0.024), metal=0.5, rough=0.32, bump=0.05,
                           bump_scale=600, dirty=False)


def gun():
    mats()
    root = bpy.data.objects.new("Gun", None)
    bpy.context.scene.collection.objects.link(root)
    parts = [
        box("Body", (0, 0.0, 0.0), (0.085, 0.32, 0.11), M["graphite"], bevel=0.03),
        box("BodyTop", (0, 0.02, 0.06), (0.06, 0.22, 0.02), M["plastic"], bevel=0.008),
        box("Glow", (0.0435, 0.0, 0.01), (0.002, 0.24, 0.008), M["glow"], bevel=0),
        box("Glow2", (-0.0435, 0.0, 0.01), (0.002, 0.24, 0.008), M["glow"], bevel=0),
        box("Grip", (0, 0.12, -0.12), (0.055, 0.07, 0.16), M["rubber"], rot=(math.radians(-18), 0, 0), bevel=0.02),
        box("Trigger", (0, 0.04, -0.075), (0.02, 0.03, 0.06), M["alu"], rot=(math.radians(-10), 0, 0), bevel=0.008),
        box("Guard", (0, 0.06, -0.11), (0.024, 0.1, 0.012), M["graphite"], bevel=0.005),
        cyl("Collar", (0, -0.18, 0.0), 0.04, 0.05, M["alu"], rot=(math.radians(90), 0, 0)),
        torus("CollarRing", (0, -0.205, 0.0), 0.04, 0.006, M["cyan"], rot=(math.radians(90), 0, 0)),
        cyl("Barrel", (0, -0.34, 0.0), 0.016, 0.28, M["alu"], rot=(math.radians(90), 0, 0)),
        torus("BarrelRing", (0, -0.42, 0.0), 0.018, 0.004, M["cyan"], rot=(math.radians(90), 0, 0)),
        cyl("Gauge", (0, -0.06, 0.085), 0.03, 0.02, M["alu"]),
        cyl("GaugeFace", (0, -0.06, 0.096), 0.025, 0.002, M["glow"]),
        tube("Hose", [Vector((0, 0.16, 0.0)), Vector((0, 0.3, -0.05)), Vector((0.05, 0.42, -0.3)),
                      Vector((0.1, 0.45, -0.7))], 0.016, M["rubber"]),
        cyl("HoseFit", (0, 0.17, 0.0), 0.028, 0.04, M["chrome"], rot=(math.radians(90), 0, 0)),
    ]
    tip = es.mesh_from_prim("cone", radius1=0.026, radius2=0.016, depth=0.05, vertices=40,
                            location=(0, -0.5, 0), rotation=(math.radians(-90), 0, 0))
    tip.data.materials.append(M["chrome"])
    es.finish_mesh(tip)
    parts.append(tip)
    for p in parts:
        p.parent = root
    root.rotation_euler = (0, 0, math.radians(-58))
    root.location = (0, 0, 0.12)
    studio()
    cam = es.camera("Cam", (1.15, -0.75, 0.5), (0.0, -0.02, 0.08), 50)
    bpy.context.scene.camera = cam
    return "gun"


def nozzles():
    mats()
    studio()

    def nozzle(x, kind):
        r = bpy.data.objects.new("N" + kind, None)
        bpy.context.scene.collection.objects.link(r)
        parts = [cyl("Base", (0, 0, 0), 0.03, 0.06, M["alu"]),
                 torus("Ring", (0, 0, 0.03), 0.03, 0.005, M["cyan"]),
                 cyl("Thread", (0, 0, -0.045), 0.022, 0.03, M["chrome"], verts=12)]
        if kind == "round":
            parts.append(cyl("Tube", (0, 0, 0.13), 0.012, 0.2, M["alu"]))
            c = es.mesh_from_prim("cone", radius1=0.022, radius2=0.012, depth=0.035, location=(0, 0, 0.245))
        elif kind == "fan":
            parts.append(cyl("Tube", (0, 0, 0.1), 0.013, 0.14, M["alu"]))
            c = es.mesh_from_prim("cone", radius1=0.013, radius2=0.045, depth=0.09, location=(0, 0, 0.215),
                                  vertices=48)
            c.scale = (1, 0.25, 1)
        else:
            parts.append(tube("Tube", [Vector((0, 0, 0.03)), Vector((0, 0, 0.15)), Vector((0, -0.06, 0.24))],
                              0.012, M["alu"]))
            c = es.mesh_from_prim("cone", radius1=0.02, radius2=0.012, depth=0.03, location=(0, -0.075, 0.255),
                                  rotation=(math.radians(-50), 0, 0))
        c.data.materials.append(M["chrome"])
        es.finish_mesh(c)
        parts.append(c)
        for p in parts:
            p.parent = r
        r.location = (x, 0, 0.05)
        r.rotation_euler = (0, 0, math.radians(25))

    nozzle(-0.17, "round")
    nozzle(0.0, "fan")
    nozzle(0.17, "angle")
    cam = es.camera("Cam", (0.0, -0.95, 0.42), (0, 0, 0.16), 60)
    bpy.context.scene.camera = cam
    return "nozzles"


def pellets():
    mats()
    rnd = random.Random(3)
    ice = bpy.data.materials.new("DryIce")
    n = ice.node_tree.nodes
    p = n["Principled BSDF"]
    p.inputs["Base Color"].default_value = (0.62, 0.68, 0.74, 1)
    p.inputs["Roughness"].default_value = 0.38
    p.inputs["Subsurface Weight"].default_value = 0.6
    p.inputs["Subsurface Radius"].default_value = (0.6, 0.8, 1.0)
    p.inputs["Subsurface Scale"].default_value = 0.004
    tx = n.new("ShaderNodeTexNoise"); tx.inputs["Scale"].default_value = 400
    bp = n.new("ShaderNodeBump"); bp.inputs["Strength"].default_value = 0.5
    ice.node_tree.links.new(tx.outputs["Fac"], bp.inputs["Height"])
    ice.node_tree.links.new(bp.outputs["Normal"], p.inputs["Normal"])
    floor = es.mesh_from_prim("plane", size=2)
    carbon = es.mat("Floor", (0.012, 0.014, 0.018), metal=0.3, rough=0.25, dirty=False)
    floor.data.materials.append(carbon)
    # шаблон гранулы: цилиндр Ø3 мм (в сцене ×10)
    proto = es.mesh_from_prim("cyl", radius=0.015, depth=0.05, vertices=16, location=(0, 0, -5))
    proto.data.materials.append(ice)
    es.finish_mesh(proto, bevel=0.004, segments=2)
    coll = bpy.context.scene.collection
    for i in range(420):
        r = abs(rnd.gauss(0, 0.16))
        a = rnd.uniform(0, 2 * math.pi)
        x, y = r * math.cos(a), r * math.sin(a) * 0.8
        h = max(0.0, 0.16 - r * 0.9)
        z = 0.015 + rnd.uniform(0, h)
        o = proto.copy()
        o.location = (x, y, z)
        o.rotation_euler = (rnd.uniform(1.2, 1.9), rnd.uniform(-0.6, 0.6), rnd.uniform(0, 6.3))
        o.scale = (1, 1, rnd.uniform(0.5, 1.3))
        coll.objects.link(o)
    fog = es.build_fog("Vapor", loc=(0, 0, 0.06), size=(1.2, 0.9, 0.2), density=0.9, anim=False)
    studio(rim_energy=420, key=35)
    cam = es.camera("Cam", (0.0, -1.0, 0.36), (0, 0.0, 0.05), 70, fstop=2.8, focus=1.0)
    bpy.context.scene.camera = cam
    return "pellets"


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "gun"
    scale = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    es.clear_scene()
    name = {"gun": gun, "nozzles": nozzles, "pellets": pellets}[mode]()
    transparent = mode != "pellets"
    w, h = (1400, 1000) if mode != "pellets" else (1600, 1000)
    es.setup_render(int(w * scale), int(h * scale), samples=56, transparent=transparent)
    bpy.context.scene.render.image_settings.color_mode = "RGBA" if transparent else "RGB"
    bpy.context.scene.render.filepath = os.path.join(OUT, f"{name}.png")
    bpy.ops.render.render(write_still=True)
