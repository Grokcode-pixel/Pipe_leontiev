"""Процедурная сцена моторного отсека V8 для сайта криочистки.

Запуск (нужен Blender 4.2+ или модуль `pip install bpy`):
    python3 render.py <режим>
или внутри Blender: Scripting → открыть этот файл → Run Script (соберёт сцену).

Главная идея: у всех материалов есть общий слой грязи, а его маска
управляется значением DirtControl.Threshold. Всё, что левее порога по оси X,
уже очищено; правее — ещё грязное. Анимируя порог и сопло вместе,
получаем «волну» криочистки.
"""
import math
import random

import bpy
from mathutils import Vector, Euler

rnd = random.Random(7)


# ----------------------------------------------------------------- helpers
def clear_scene():
    for coll in (bpy.data.objects, bpy.data.meshes, bpy.data.curves,
                 bpy.data.materials, bpy.data.lights, bpy.data.cameras,
                 bpy.data.node_groups, bpy.data.worlds):
        for item in list(coll):
            coll.remove(item)


def link(obj):
    bpy.context.scene.collection.objects.link(obj)
    return obj


def finish_mesh(obj, bevel=0.0, segments=3, smooth=True):
    if smooth:
        obj.data.polygons.foreach_set("use_smooth", [True] * len(obj.data.polygons))
    if bevel > 0:
        m = obj.modifiers.new("Bevel", "BEVEL")
        m.width = bevel
        m.segments = segments
        m.limit_method = "ANGLE"
        m.harden_normals = True
    obj.modifiers.new("WN", "WEIGHTED_NORMAL").keep_sharp = True
    return obj


def mesh_from_prim(kind, **kw):
    fn = {
        "cube": bpy.ops.mesh.primitive_cube_add,
        "cyl": bpy.ops.mesh.primitive_cylinder_add,
        "torus": bpy.ops.mesh.primitive_torus_add,
        "sphere": bpy.ops.mesh.primitive_uv_sphere_add,
        "cone": bpy.ops.mesh.primitive_cone_add,
        "plane": bpy.ops.mesh.primitive_plane_add,
    }[kind]
    fn(**kw)
    return bpy.context.active_object


def box(name, loc, size, mat, rot=(0, 0, 0), bevel=0.006):
    o = mesh_from_prim("cube", size=1, location=loc, rotation=rot)
    o.name = name
    o.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    o.data.materials.append(mat)
    return finish_mesh(o, bevel, smooth=False)


def cyl(name, loc, r, depth, mat, rot=(0, 0, 0), verts=40, bevel=0.003):
    o = mesh_from_prim("cyl", radius=r, depth=depth, vertices=verts, location=loc, rotation=rot)
    o.name = name
    o.data.materials.append(mat)
    return finish_mesh(o, bevel)


def torus(name, loc, R, r, mat, rot=(0, 0, 0)):
    o = mesh_from_prim("torus", major_radius=R, minor_radius=r, major_segments=48,
                       minor_segments=16, location=loc, rotation=rot)
    o.name = name
    o.data.materials.append(mat)
    return finish_mesh(o)


def tube(name, pts, r, mat, res=12):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = r
    cu.bevel_resolution = 4
    cu.resolution_u = res
    cu.use_fill_caps = True
    sp = cu.splines.new("BEZIER")
    sp.bezier_points.add(len(pts) - 1)
    for bp, p in zip(sp.bezier_points, pts):
        bp.co = p
        bp.handle_left_type = bp.handle_right_type = "AUTO"
    o = bpy.data.objects.new(name, cu)
    o.data.materials.append(mat)
    return link(o)


# ----------------------------------------------------------------- materials
def dirt_group():
    """Общая группа: Threshold — положение фронта очистки по X."""
    g = bpy.data.node_groups.get("DirtControl")
    if g:
        return g
    g = bpy.data.node_groups.new("DirtControl", "ShaderNodeTree")
    g.interface.new_socket("Dirt", in_out="OUTPUT", socket_type="NodeSocketFloat")
    g.interface.new_socket("Frost", in_out="OUTPUT", socket_type="NodeSocketFloat")
    n, l = g.nodes, g.links
    out = n.new("NodeGroupOutput")
    thr = n.new("ShaderNodeValue")
    thr.name = thr.label = "Threshold"
    thr.outputs[0].default_value = -5.0
    geo = n.new("ShaderNodeNewGeometry")
    sep = n.new("ShaderNodeSeparateXYZ")
    l.new(geo.outputs["Position"], sep.inputs[0])
    # слегка «рваный» фронт очистки
    wob = n.new("ShaderNodeTexNoise")
    wob.inputs["Scale"].default_value = 6
    l.new(geo.outputs["Position"], wob.inputs["Vector"])
    wobm = n.new("ShaderNodeMath"); wobm.operation = "MULTIPLY_ADD"
    l.new(wob.outputs["Fac"], wobm.inputs[0]); wobm.inputs[1].default_value = 0.12
    l.new(sep.outputs["X"], wobm.inputs[2])
    d = n.new("ShaderNodeMath"); d.operation = "SUBTRACT"
    l.new(wobm.outputs[0], d.inputs[0]); l.new(thr.outputs[0], d.inputs[1])
    # Dirt = smoothstep(d, -0.03..0.03)
    mr = n.new("ShaderNodeMapRange"); mr.interpolation_type = "SMOOTHSTEP"
    mr.inputs["From Min"].default_value = -0.03
    mr.inputs["From Max"].default_value = 0.03
    l.new(d.outputs[0], mr.inputs["Value"])
    # базовая грязь: шум + щели (AO)
    nz = n.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 3.5; nz.inputs["Detail"].default_value = 8
    nz.inputs["Roughness"].default_value = 0.65
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.42
    ramp.color_ramp.elements[1].position = 0.68
    l.new(nz.outputs["Fac"], ramp.inputs[0])
    ao = n.new("ShaderNodeAmbientOcclusion")
    ao.inputs["Distance"].default_value = 0.08
    inv = n.new("ShaderNodeMath"); inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    l.new(ao.outputs["AO"], inv.inputs[1])
    mx = n.new("ShaderNodeMath"); mx.operation = "MAXIMUM"
    l.new(ramp.outputs["Color"], mx.inputs[0])
    aom = n.new("ShaderNodeMath"); aom.operation = "MULTIPLY"
    l.new(inv.outputs[0], aom.inputs[0]); aom.inputs[1].default_value = 2.5
    l.new(aom.outputs[0], mx.inputs[1])
    cov = n.new("ShaderNodeMath"); cov.operation = "MULTIPLY_ADD"
    l.new(mx.outputs[0], cov.inputs[0]); cov.inputs[1].default_value = 0.45
    cov.inputs[2].default_value = 0.55
    fin = n.new("ShaderNodeMath"); fin.operation = "MULTIPLY"; fin.use_clamp = True
    l.new(cov.outputs[0], fin.inputs[0]); l.new(mr.outputs[0], fin.inputs[1])
    l.new(fin.outputs[0], out.inputs["Dirt"])
    # иней — узкая полоса на фронте сублимации
    ab = n.new("ShaderNodeMath"); ab.operation = "ABSOLUTE"
    off = n.new("ShaderNodeMath"); off.operation = "ADD"
    l.new(d.outputs[0], off.inputs[0]); off.inputs[1].default_value = 0.03
    l.new(off.outputs[0], ab.inputs[0])
    fr = n.new("ShaderNodeMapRange")
    fr.inputs["From Min"].default_value = 0.035
    fr.inputs["From Max"].default_value = 0.0
    l.new(ab.outputs[0], fr.inputs["Value"])
    frn = n.new("ShaderNodeMath"); frn.operation = "MULTIPLY"; frn.use_clamp = True
    l.new(fr.outputs[0], frn.inputs[0]); l.new(ramp.outputs["Color"], frn.inputs[1])
    frn2 = n.new("ShaderNodeMath"); frn2.operation = "MULTIPLY"; frn2.use_clamp = True
    l.new(frn.outputs[0], frn2.inputs[0]); frn2.inputs[1].default_value = 1.2
    l.new(frn2.outputs[0], out.inputs["Frost"])
    return g


def set_threshold(v, frame=None):
    node = dirt_group().nodes["Threshold"]
    node.outputs[0].default_value = v
    if frame is not None:
        node.outputs[0].keyframe_insert("default_value", frame=frame)


def mat(name, color, metal=0.0, rough=0.5, coat=0.0, bump=0.0, bump_scale=60,
        dirty=True, emission=None, wrinkle=False):
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    n, l = nt.nodes, nt.links
    for x in list(n):
        n.remove(x)
    out = n.new("ShaderNodeOutputMaterial")
    clean = n.new("ShaderNodeBsdfPrincipled")
    clean.inputs["Base Color"].default_value = (*color, 1)
    clean.inputs["Metallic"].default_value = metal
    clean.inputs["Roughness"].default_value = rough
    clean.inputs["Coat Weight"].default_value = coat
    clean.inputs["Coat Roughness"].default_value = 0.08
    if emission:
        clean.inputs["Emission Color"].default_value = (*emission[0], 1)
        clean.inputs["Emission Strength"].default_value = emission[1]
    if bump > 0 or wrinkle:
        tx = n.new("ShaderNodeTexNoise")
        tx.inputs["Scale"].default_value = bump_scale if not wrinkle else 260
        tx.inputs["Detail"].default_value = 6 if not wrinkle else 2
        bp = n.new("ShaderNodeBump")
        bp.inputs["Strength"].default_value = bump if not wrinkle else 0.35
        bp.inputs["Distance"].default_value = 0.002
        l.new(tx.outputs["Fac"], bp.inputs["Height"])
        l.new(bp.outputs["Normal"], clean.inputs["Normal"])
    if not dirty:
        l.new(clean.outputs[0], out.inputs["Surface"])
        return m
    grp = n.new("ShaderNodeGroup"); grp.node_tree = dirt_group()
    # грязный слой: масляный нагар + пыль/реагенты
    dirt = n.new("ShaderNodeBsdfPrincipled")
    dn = n.new("ShaderNodeTexNoise")
    dn.inputs["Scale"].default_value = 9; dn.inputs["Detail"].default_value = 12
    cr = n.new("ShaderNodeValToRGB")
    cr.color_ramp.elements[0].color = (0.010, 0.008, 0.005, 1)   # масло/нагар
    cr.color_ramp.elements[1].color = (0.15, 0.12, 0.085, 1)     # дорожная пыль
    cr.color_ramp.elements[0].position = 0.45
    cr.color_ramp.elements[1].position = 0.75
    l.new(dn.outputs["Fac"], cr.inputs[0])
    l.new(cr.outputs["Color"], dirt.inputs["Base Color"])
    rr = n.new("ShaderNodeMapRange")
    rr.inputs["To Min"].default_value = 0.22; rr.inputs["To Max"].default_value = 0.95
    l.new(dn.outputs["Fac"], rr.inputs["Value"])
    l.new(rr.outputs[0], dirt.inputs["Roughness"])
    db = n.new("ShaderNodeBump"); db.inputs["Strength"].default_value = 0.6
    db.inputs["Distance"].default_value = 0.003
    l.new(dn.outputs["Fac"], db.inputs["Height"])
    l.new(db.outputs["Normal"], dirt.inputs["Normal"])
    frost = n.new("ShaderNodeBsdfPrincipled")
    frost.inputs["Base Color"].default_value = (0.85, 0.95, 1.0, 1)
    frost.inputs["Roughness"].default_value = 0.85
    frost.inputs["Emission Color"].default_value = (0.4, 0.9, 1.0, 1)
    frost.inputs["Emission Strength"].default_value = 0.3
    m1 = n.new("ShaderNodeMixShader")
    l.new(grp.outputs["Dirt"], m1.inputs[0])
    l.new(clean.outputs[0], m1.inputs[1]); l.new(dirt.outputs[0], m1.inputs[2])
    m2 = n.new("ShaderNodeMixShader")
    l.new(grp.outputs["Frost"], m2.inputs[0])
    l.new(m1.outputs[0], m2.inputs[1]); l.new(frost.outputs[0], m2.inputs[2])
    l.new(m2.outputs[0], out.inputs["Surface"])
    return m


def volume_mat(name, density, scale=3.0, color=(0.75, 0.93, 1.0), emit=0.0, anim=False):
    m = bpy.data.materials.new(name)
    n, l = m.node_tree.nodes, m.node_tree.links
    for x in list(n):
        n.remove(x)
    out = n.new("ShaderNodeOutputMaterial")
    pv = n.new("ShaderNodeVolumePrincipled")
    pv.inputs["Color"].default_value = (*color, 1)
    pv.inputs["Anisotropy"].default_value = 0.35
    pv.inputs["Emission Color"].default_value = (0.3, 0.85, 1.0, 1)
    pv.inputs["Emission Strength"].default_value = emit
    tc = n.new("ShaderNodeTexCoord")
    mp = n.new("ShaderNodeMapping")
    l.new(tc.outputs["Object"], mp.inputs["Vector"])
    if anim:
        mp.inputs["Location"].default_value = (0, 0, 0)
        mp.inputs["Location"].keyframe_insert("default_value", frame=1)
        mp.inputs["Location"].default_value = (0.4, 0.2, -0.9)
        mp.inputs["Location"].keyframe_insert("default_value", frame=120)
    nz = n.new("ShaderNodeTexNoise")
    nz.noise_dimensions = "3D"
    nz.inputs["Scale"].default_value = scale
    nz.inputs["Detail"].default_value = 6
    nz.inputs["Roughness"].default_value = 0.6
    l.new(mp.outputs[0], nz.inputs["Vector"])
    ramp = n.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].position = 0.45
    ramp.color_ramp.elements[1].position = 0.8
    l.new(nz.outputs["Fac"], ramp.inputs[0])
    # затухание к краям объёма (сферический градиент)
    gr = n.new("ShaderNodeTexGradient"); gr.gradient_type = "SPHERICAL"
    l.new(tc.outputs["Object"], gr.inputs["Vector"])
    mul = n.new("ShaderNodeMath"); mul.operation = "MULTIPLY"
    l.new(ramp.outputs["Color"], mul.inputs[0]); l.new(gr.outputs["Fac"], mul.inputs[1])
    mul2 = n.new("ShaderNodeMath"); mul2.operation = "MULTIPLY"
    l.new(mul.outputs[0], mul2.inputs[0]); mul2.inputs[1].default_value = density
    l.new(mul2.outputs[0], pv.inputs["Density"])
    l.new(pv.outputs[0], out.inputs["Volume"])
    return m


def jet_mat():
    m = bpy.data.materials.new("Jet")
    n, l = m.node_tree.nodes, m.node_tree.links
    for x in list(n):
        n.remove(x)
    out = n.new("ShaderNodeOutputMaterial")
    pv = n.new("ShaderNodeVolumePrincipled")
    pv.inputs["Color"].default_value = (0.9, 0.97, 1.0, 1)
    pv.inputs["Emission Color"].default_value = (0.35, 0.9, 1.0, 1)
    tc = n.new("ShaderNodeTexCoord")
    nz = n.new("ShaderNodeTexNoise"); nz.inputs["Scale"].default_value = 9
    nz.inputs["Detail"].default_value = 4
    l.new(tc.outputs["Object"], nz.inputs["Vector"])
    gr = n.new("ShaderNodeTexGradient"); gr.gradient_type = "SPHERICAL"
    l.new(tc.outputs["Object"], gr.inputs["Vector"])
    mul = n.new("ShaderNodeMath"); mul.operation = "MULTIPLY"
    l.new(nz.outputs["Fac"], mul.inputs[0]); l.new(gr.outputs["Fac"], mul.inputs[1])
    d = n.new("ShaderNodeMath"); d.operation = "MULTIPLY"
    l.new(mul.outputs[0], d.inputs[0]); d.inputs[1].default_value = 5
    e = n.new("ShaderNodeMath"); e.operation = "MULTIPLY"
    l.new(mul.outputs[0], e.inputs[0]); e.inputs[1].default_value = 1.6
    l.new(d.outputs[0], pv.inputs["Density"])
    l.new(e.outputs[0], pv.inputs["Emission Strength"])
    l.new(pv.outputs[0], out.inputs["Volume"])
    return m


# ----------------------------------------------------------------- scene
M = {}


def materials():
    M["paint"] = mat("CarPaint", (0.012, 0.014, 0.018), metal=0.6, rough=0.32, coat=1.0, dirty=False)
    M["bay"] = mat("BayMetal", (0.014, 0.015, 0.018), metal=0.5, rough=0.55)
    M["alu"] = mat("PolishedAlu", (0.92, 0.93, 0.95), metal=1, rough=0.14)
    M["cast"] = mat("CastAlu", (0.62, 0.63, 0.65), metal=1, rough=0.42, bump=0.25, bump_scale=180)
    M["wrinkle"] = mat("WrinkleBlack", (0.025, 0.027, 0.03), metal=0.2, rough=0.55, wrinkle=True)
    M["plastic"] = mat("BlackPlastic", (0.018, 0.019, 0.021), rough=0.42, bump=0.08, bump_scale=400)
    M["rubber"] = mat("Rubber", (0.012, 0.012, 0.013), rough=0.62)
    M["chrome"] = mat("Bolt", (0.85, 0.86, 0.88), metal=1, rough=0.22)
    M["iron"] = mat("CastIron", (0.09, 0.09, 0.095), metal=0.8, rough=0.6, bump=0.3, bump_scale=120)
    M["felt"] = mat("HoodFelt", (0.035, 0.036, 0.04), rough=0.95, bump=0.4, bump_scale=90)
    M["white"] = mat("TankPlastic", (0.62, 0.62, 0.6), rough=0.35)
    M["grey"] = mat("GreyConnector", (0.16, 0.17, 0.19), rough=0.45)
    M["red"] = mat("RedCap", (0.5, 0.02, 0.02), rough=0.35)
    M["yellow"] = mat("YellowCap", (0.75, 0.45, 0.02), rough=0.35)
    M["cyan"] = mat("CyanAnodized", (0.0, 0.55, 0.75), metal=1, rough=0.25)
    M["glow"] = mat("CyanGlow", (0, 0, 0), emission=((0.0, 0.9, 1.0), 25), dirty=False)
    M["rad"] = mat("RadiatorCore", (0.05, 0.05, 0.055), metal=0.7, rough=0.4)


def build_bay():
    # пол и стены моторного отсека
    box("BayFloor", (0, 0, -0.12), (1.8, 1.6, 0.04), M["bay"])
    for s in (-1, 1):
        box(f"InnerFender{s}", (s * 0.82, 0, 0.2), (0.06, 1.5, 0.66), M["bay"], bevel=0.02)
        box(f"FenderTop{s}", (s * 0.86, -0.05, 0.56), (0.14, 1.6, 0.05), M["paint"], bevel=0.02)
        # чашки амортизаторов и болты
        cyl(f"StrutTower{s}", (s * 0.64, 0.34, 0.33), 0.11, 0.42, M["bay"], bevel=0.02)
        for i in range(3):
            a = i * 2 * math.pi / 3 + 0.4
            cyl(f"StrutBolt{s}{i}", (s * 0.64 + 0.07 * math.cos(a), 0.34 + 0.07 * math.sin(a), 0.545),
                0.012, 0.02, M["chrome"], verts=6)
        cyl(f"StrutTop{s}", (s * 0.64, 0.34, 0.55), 0.03, 0.03, M["iron"])
    # распорка стоек: полированный алюминий + анодированные чашки
    tube("StrutBar", [Vector((-0.64, 0.34, 0.6)), Vector((0, 0.42, 0.66)), Vector((0.64, 0.34, 0.6))],
         0.018, M["alu"])
    for s in (-1, 1):
        cyl(f"StrutCap{s}", (s * 0.64, 0.34, 0.585), 0.06, 0.03, M["cyan"], bevel=0.006)
    # моторный щит
    box("Firewall", (0, 0.72, 0.25), (1.6, 0.06, 0.8), M["bay"], bevel=0.02)
    box("FirewallPad", (0, 0.685, 0.28), (1.2, 0.02, 0.5), M["felt"], bevel=0.01)
    box("Cowl", (0, 0.66, 0.62), (1.62, 0.18, 0.05), M["plastic"], bevel=0.015)
    # передняя панель и радиатор
    box("RadSupport", (0, -0.74, 0.42), (1.6, 0.1, 0.06), M["plastic"], bevel=0.01)
    box("Radiator", (0, -0.73, 0.18), (1.2, 0.05, 0.44), M["rad"], bevel=0.005)
    tube("RadTop", [Vector((-0.6, -0.7, 0.385)), Vector((0.6, -0.7, 0.385))], 0.02, M["plastic"])
    # капот (открыт) с шумкой
    hood = box("Hood", (0, 0.0, 0.0), (1.66, 1.5, 0.03), M["paint"], bevel=0.02)
    pad = box("HoodPad", (0, 0.0, -0.025), (1.4, 1.25, 0.02), M["felt"], bevel=0.01)
    pivot = bpy.data.objects.new("HoodPivot", None)
    link(pivot)
    pivot.location = (0, 0.74, 0.64)
    for o in (hood, pad):
        o.parent = pivot
        o.location = (o.location.x, -0.75, o.location.z)
    pivot.rotation_euler = (math.radians(-62), 0, 0)


def build_engine():
    # блок цилиндров
    box("Block", (0, 0.0, 0.12), (0.44, 0.66, 0.34), M["iron"], bevel=0.02)
    for s in (-1, 1):
        rot = (0, s * math.radians(-32), 0)
        cx = s * 0.21
        box(f"Head{s}", (cx, 0.0, 0.32), (0.2, 0.66, 0.12), M["cast"], rot=rot, bevel=0.01)
        # клапанная крышка
        off = Vector((s * 0.035, 0, 0.085))
        vc = Vector((cx, 0, 0.32)) + off
        box(f"ValveCover{s}", vc, (0.19, 0.64, 0.075), M["wrinkle"], rot=rot, bevel=0.025)
        # полированные рёбра
        e = Euler(rot)
        up = Vector((0, 0, 1)); up.rotate(e)
        for i in range(9):
            y = -0.24 + i * 0.06
            p = vc + up * 0.04 + Vector((0, y, 0))
            box(f"Fin{s}{i}", p, (0.15, 0.012, 0.014), M["alu"], rot=rot, bevel=0.004)
        # болты по периметру
        side = Vector((1, 0, 0)); side.rotate(e)
        for i in range(5):
            y = -0.28 + i * 0.14
            for k in (-1, 1):
                p = vc + side * (k * 0.088) + up * 0.03 + Vector((0, y, 0))
                cyl(f"VCBolt{s}{i}{k}", p, 0.008, 0.014, M["chrome"], rot=rot, verts=6, bevel=0.001)
        # катушки зажигания на внутренней стороне
        for i in range(4):
            y = -0.21 + i * 0.14
            p = vc + side * (-s * 0.06) + up * 0.055 + Vector((0, y, 0))
            box(f"Coil{s}{i}", p, (0.045, 0.06, 0.05), M["plastic"], rot=rot, bevel=0.008)
            box(f"CoilPlug{s}{i}", p + up * 0.03 + side * (-s * 0.012), (0.022, 0.03, 0.018),
                M["grey"], rot=rot, bevel=0.004)
        # жгут проводки к катушкам
        pts = []
        for i in range(5):
            y = -0.3 + i * 0.15
            pts.append(vc + side * (-s * 0.085) + up * 0.09 + Vector((0, y, 0.005 * math.sin(i))))
        tube(f"CoilHarness{s}", pts, 0.009, M["rubber"])
        # нижний жгут вдоль блока
        tube(f"LowHarness{s}", [Vector((s * 0.29, -0.36, 0.16)), Vector((s * 0.3, -0.1, 0.2)),
                                Vector((s * 0.31, 0.2, 0.17)), Vector((s * 0.36, 0.45, 0.25)),
                                Vector((s * 0.5, 0.62, 0.35))], 0.012, M["rubber"])
        for i, y in enumerate((-0.2, 0.08, 0.32)):
            box(f"Sensor{s}{i}", (s * 0.31, y, 0.2), (0.03, 0.04, 0.03), M["grey"], bevel=0.005)

    # впускной ресивер
    box("Plenum", (0, 0.02, 0.45), (0.17, 0.56, 0.11), M["cast"], bevel=0.035)
    for i in range(6):
        box(f"PlenumRib{i}", (0, -0.2 + i * 0.08, 0.508), (0.13, 0.01, 0.012), M["cast"], bevel=0.003)
    # впускные каналы
    for s in (-1, 1):
        for i in range(4):
            y = -0.21 + i * 0.14
            tube(f"Runner{s}{i}", [Vector((s * 0.06, y, 0.47)), Vector((s * 0.11, y, 0.5)),
                                   Vector((s * 0.16, y, 0.43))], 0.022, M["cast"], res=8)
    # дроссель и полированный впуск
    cyl("Throttle", (0, -0.3, 0.45), 0.055, 0.08, M["alu"], rot=(math.radians(90), 0, 0))
    torus("ThrottleRing", (0, -0.34, 0.45), 0.055, 0.008, M["cyan"], rot=(math.radians(90), 0, 0))
    tube("IntakePipe", [Vector((0, -0.34, 0.45)), Vector((0, -0.45, 0.47)),
                        Vector((-0.25, -0.5, 0.45)), Vector((-0.5, -0.42, 0.42))], 0.04, M["alu"])
    torus("IntakeClamp", (0, -0.4, 0.46), 0.05, 0.006, M["chrome"], rot=(math.radians(90), 0, 0))
    # корпус воздушного фильтра
    box("Airbox", (-0.56, -0.36, 0.34), (0.3, 0.34, 0.18), M["plastic"], bevel=0.03)
    for i in range(5):
        box(f"AirRib{i}", (-0.56, -0.48 + i * 0.06, 0.432), (0.26, 0.012, 0.01), M["plastic"], bevel=0.003)
    # турбина справа спереди + интеркулерный патрубок
    cyl("TurboBody", (0.47, -0.4, 0.3), 0.075, 0.09, M["cast"], rot=(0, math.radians(90), 0))
    torus("TurboScroll", (0.47, -0.4, 0.3), 0.085, 0.035, M["cast"], rot=(0, math.radians(90), 0))
    cyl("TurboInlet", (0.42, -0.4, 0.3), 0.045, 0.06, M["alu"], rot=(0, math.radians(90), 0))
    torus("TurboRing", (0.39, -0.4, 0.3), 0.046, 0.007, M["cyan"], rot=(0, math.radians(90), 0))
    tube("ChargePipe", [Vector((0.47, -0.4, 0.4)), Vector((0.48, -0.5, 0.5)),
                        Vector((0.3, -0.56, 0.5)), Vector((0.1, -0.4, 0.47))], 0.032, M["alu"])
    box("HeatShield", (0.56, -0.36, 0.22), (0.05, 0.22, 0.16), M["chrome"], bevel=0.01)
    # передний привод: шкивы и ремень
    for x, z, r in ((0, 0.1, 0.09), (0.16, 0.28, 0.05), (-0.17, 0.26, 0.055), (0.12, 0.0, 0.045)):
        cyl(f"Pulley{x}{z}", (x, -0.36, z), r, 0.035, M["chrome"], rot=(math.radians(90), 0, 0))
    box("Alternator", (-0.26, -0.33, 0.27), (0.12, 0.12, 0.12), M["cast"], bevel=0.03)
    # маслозаливная крышка
    cyl("OilCap", (-0.25, 0.18, 0.47), 0.03, 0.025, M["yellow"], rot=(0, math.radians(32), 0))
    # патрубки охлаждения
    tube("UpperHose", [Vector((0.05, -0.34, 0.36)), Vector((0.12, -0.5, 0.4)),
                       Vector((0.35, -0.62, 0.36)), Vector((0.45, -0.7, 0.34))], 0.026, M["rubber"])
    for p in ((0.06, -0.37, 0.37), (0.43, -0.69, 0.345)):
        torus("HoseClamp", p, 0.028, 0.005, M["chrome"], rot=(math.radians(70), 0, math.radians(30)))
    tube("HeaterHose", [Vector((0.2, 0.3, 0.3)), Vector((0.35, 0.45, 0.38)), Vector((0.45, 0.62, 0.4))],
         0.016, M["rubber"])
    # расширительный бачок, бачок тормозной, АКБ, блок предохранителей
    box("CoolantTank", (0.6, 0.06, 0.34), (0.16, 0.24, 0.14), M["white"], bevel=0.03)
    cyl("CoolantCap", (0.6, 0.0, 0.42), 0.032, 0.03, M["plastic"])
    box("Battery", (-0.6, 0.1, 0.27), (0.18, 0.3, 0.2), M["plastic"], bevel=0.01)
    box("BatTerm", (-0.6, 0.0, 0.38), (0.06, 0.05, 0.03), M["red"], bevel=0.006)
    box("FuseBox", (-0.6, 0.46, 0.32), (0.16, 0.2, 0.08), M["plastic"], bevel=0.015)
    cyl("BrakeRes", (-0.32, 0.6, 0.4), 0.05, 0.08, M["white"])
    cyl("BrakeCap", (-0.32, 0.6, 0.45), 0.035, 0.02, M["plastic"])
    # декоративная крышка с подсветкой-индикатором
    box("LogoPlate", (0, 0.2, 0.505), (0.09, 0.14, 0.006), M["plastic"], bevel=0.002)
    box("LogoGlow", (0, 0.2, 0.509), (0.06, 0.006, 0.002), M["glow"], bevel=0.0)


def build_blaster():
    """Сопло криопистолета, которое ведёт струю по двигателю."""
    root = bpy.data.objects.new("Blaster", None)
    link(root)
    parts = []
    parts.append(cyl("Nozzle", (0, 0, 0.0), 0.012, 0.36, M["alu"], verts=24))
    parts.append(cyl("NozzleTip", (0, 0, -0.19), 0.02, 0.04, M["chrome"], verts=24))
    parts.append(torus("NozzleRing", (0, 0, 0.1), 0.016, 0.004, M["cyan"]))
    parts.append(box("Gun", (0, 0.02, 0.26), (0.06, 0.12, 0.18), M["plastic"], bevel=0.02))
    parts.append(box("GunGlow", (0.031, 0.02, 0.28), (0.002, 0.06, 0.012), M["glow"], bevel=0))
    parts.append(tube("GunHose", [Vector((0, 0.06, 0.35)), Vector((0, 0.2, 0.6)), Vector((0.1, 0.3, 1.2))],
                      0.022, M["rubber"]))
    for p in parts:
        p.parent = root
    jet = mesh_from_prim("cone", radius1=0.05, radius2=0.01, depth=0.34, vertices=32,
                         location=(0, 0, -0.38))
    jet.name = "Jet"
    jet.data.materials.append(jet_mat())
    jet.parent = root
    return root


def build_fog(name="Fog", loc=(0, -0.1, 0.45), size=(1.5, 1.4, 0.45), density=0.6, anim=True):
    o = mesh_from_prim("cube", size=1, location=loc)
    o.name = name
    o.scale = size
    o.data.materials.append(volume_mat(name + "Mat", density, anim=anim))
    return o


def build_world_and_lights():
    w = bpy.data.worlds.new("World")
    bpy.context.scene.world = w
    bg = w.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.004, 0.005, 0.007, 1)
    bg.inputs["Strength"].default_value = 1.0

    def area(name, loc, rot, size, energy, color, shape="RECTANGLE", sy=None):
        ld = bpy.data.lights.new(name, "AREA")
        ld.energy = energy
        ld.color = color
        ld.shape = shape
        ld.size = size
        if sy:
            ld.size_y = sy
        o = bpy.data.objects.new(name, ld)
        o.location = loc
        o.rotation_euler = rot
        return link(o)

    # тёплый-нейтральный софтбокс сверху (как под капотом в студии)
    area("Key", (0.3, -0.4, 1.9), (math.radians(12), math.radians(8), 0), 1.6, 150,
         (1.0, 0.96, 0.92), sy=0.6)
    # ледяной циановый контровой сзади
    area("RimCyan", (0, 1.4, 1.2), (math.radians(-55), 0, 0), 1.8, 520, (0.15, 0.85, 1.0), sy=0.3)
    # боковые полосы для бликов на алюминии
    area("StripL", (-1.4, -0.4, 0.9), (0, math.radians(-60), 0), 0.15, 120, (0.7, 0.9, 1.0), sy=1.6)
    area("StripR", (1.4, -0.2, 0.9), (0, math.radians(60), 0), 0.15, 90, (1.0, 1.0, 1.0), sy=1.6)
    # подсветка тумана снизу
    pl = bpy.data.lights.new("UnderGlow", "POINT")
    pl.energy = 25
    pl.color = (0.1, 0.8, 1.0)
    pl.shadow_soft_size = 0.3
    o = bpy.data.objects.new("UnderGlow", pl)
    o.location = (0, -0.5, 0.1)
    link(o)


def camera(name, loc, target, lens=35, fstop=None, focus=None):
    cd = bpy.data.cameras.new(name)
    cd.lens = lens
    cd.sensor_width = 36
    co = bpy.data.objects.new(name, cd)
    link(co)
    co.location = loc
    d = Vector(target) - Vector(loc)
    co.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
    if fstop:
        cd.dof.use_dof = True
        cd.dof.aperture_fstop = fstop
        cd.dof.focus_distance = focus if focus else d.length
    return co


def setup_render(w, h, samples=96, transparent=False):
    s = bpy.context.scene
    s.render.engine = "CYCLES"
    s.cycles.device = "CPU"
    s.cycles.samples = samples
    s.cycles.use_adaptive_sampling = True
    s.cycles.adaptive_threshold = 0.02
    s.cycles.use_denoising = True
    s.cycles.max_bounces = 6
    s.cycles.volume_bounces = 1
    s.cycles.volume_step_rate = 4.0
    s.cycles.volume_max_steps = 256
    s.cycles.caustics_reflective = False
    s.cycles.caustics_refractive = False
    s.cycles.blur_glossy = 1.0
    s.cycles.sample_clamp_indirect = 6
    s.render.resolution_x = w
    s.render.resolution_y = h
    s.render.resolution_percentage = 100
    s.render.film_transparent = transparent
    s.view_settings.view_transform = "AgX"
    s.view_settings.look = "AgX - Punchy"
    s.view_settings.exposure = 0.0


def build_engine_scene():
    clear_scene()
    materials()
    build_bay()
    build_engine()
    build_world_and_lights()
