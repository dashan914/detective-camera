"""Web-only export of the existing V33 assembly; never modifies its source."""
import bpy
from pathlib import Path
from mathutils import Matrix

root = Path(__file__).resolve().parent
source = root.parent / 'hardware/cad/DASHAN_V33.blend'
bpy.ops.wm.open_mainfile(filepath=str(source))
parts = list(bpy.data.collections['01_PRINT_PARTS_V1'].objects)
references = [bpy.data.objects[n] for n in ['ESP32', 'MY628', 'Battery', 'Controller', 'Buck', 'Paper roll', 'OV5640_visual_only', 'REF_LCD183_glass_R6_PROVISIONAL', 'REF_LCD183_PCB_ENVELOPE', 'REF_active_area'] if n in bpy.data.objects]
parts += references
palette = {'ivory': 'e5dfd0', 'black': '272a2b', 'red': 'cc5038', 'orange': 'cd7e48', 'yellow': 'd4ba66', 'blue': '648b9a', 'green': '3e8064', 'metal': '777e82', 'paper': 'f5f0e6', 'glass': '12272c'}
materials = {}
for name, color in palette.items():
    m = bpy.data.materials.new('Web ' + name); m.use_nodes = True
    rgb = [int(color[i:i+2], 16) / 255 for i in (0, 2, 4)]
    rgb = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb]
    m.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value = (*rgb, 1)
    m.node_tree.nodes.get('Principled BSDF').inputs['Roughness'].default_value = .43
    materials[name] = m
bpy.ops.object.select_all(action='DESELECT')
for o in parts:
    if o.type != 'MESH': continue
    o.hide_set(False); o.hide_viewport = False; o.hide_render = False; o.select_set(True)
    transform = o.matrix_world.copy()
    for vertex in o.data.vertices: vertex.co = (transform @ vertex.co) * .001
    o.matrix_world = Matrix.Identity(4)
    name = o.name; color = 'black'
    if name.startswith(('01_', '05_', '23_')): color = 'ivory'
    if name.startswith('06_'): color = 'red'
    if name.startswith('10_'): color = ['orange', 'yellow', 'blue'][int(name[-1])]
    if name in ('ESP32', 'Controller'): color = 'green'
    if name == 'Battery' or 'PCB_ENVELOPE' in name: color = 'blue'
    if name == 'MY628': color = 'metal'
    if name == 'Paper roll': color = 'paper'
    if name == 'OV5640_visual_only' or 'glass' in name or name == 'REF_active_area': color = 'glass'
    o.data.materials.clear(); o.data.materials.append(materials[color])
    for face in o.data.polygons: face.material_index = 0
    for key in list(o.keys()): del o[key]
    o['part_id'] = name
    o['role'] = 'display_surface' if name == 'REF_active_area' else 'display_glass' if 'glass' in name else 'reference' if o in references else 'print_part'
    if name == 'REF_active_area':
        layer = o.data.uv_layers.new(name='Display UV')
        for loop in o.data.loops:
            v = o.data.vertices[loop.vertex_index].co
            layer.data[loop.index].uv = ((v.x + .017465) / .03493, (v.y + .006 + .01476) / .02952)
    o.data.update()
bpy.context.scene.unit_settings.scale_length = 1
bpy.ops.export_scene.gltf(filepath=str(root / 'DASHAN_V33.glb'), export_format='GLB', use_selection=True, export_extras=True, export_yup=True, export_cameras=False, export_lights=False, export_materials='EXPORT', export_draco_mesh_compression_enable=True, export_draco_mesh_compression_level=6, export_draco_position_quantization=16, export_draco_normal_quantization=12, export_draco_texcoord_quantization=14)
print('V33 web export', len(parts), (root / 'DASHAN_V33.glb').stat().st_size)
