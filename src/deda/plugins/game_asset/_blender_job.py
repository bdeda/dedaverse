# ###################################################################################
#
# Copyright 2025 Ben Deda
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# ###################################################################################
"""The optimizer pipeline. Runs inside Blender, started by :mod:`._runner`::

    blender --background --factory-startup --python _blender_job.py -- job.json

Steps: import -> weld + decimate to the triangle budget -> unwrap (flat assets: planar projection of
each side of the mid-plane; others: seams found on a smoothed copy) -> bake BaseColor / Normal / ORM
from the source -> export FBX and/or GLB -> write a JSON result.

Functions that call ``bpy`` only work inside Blender. They are excluded from unit-test coverage and
exercised by ``tests/test_game_asset_blender.py``, which runs this job in a real Blender when one is
installed. The orchestration in :func:`run` and :func:`main` is unit-tested with those functions patched.
"""
__all__ = ['main', 'run']

import json
import math
import sys
import time
import traceback
from contextlib import contextmanager
from pathlib import Path

import numpy as np

try:
    from . import _metrics, _symmetry
    from ._options import OptimizeError, OptimizeOptions, OptimizeResult
except ImportError:  # pragma: no cover - started as a script inside Blender, outside the deda package
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import _metrics  # type: ignore[no-redef]  # pylint: disable=import-error
    import _symmetry  # type: ignore[no-redef]  # pylint: disable=import-error
    from _options import OptimizeError, OptimizeOptions, OptimizeResult  # type: ignore[no-redef]  # pylint: disable=import-error

ERROR_SAMPLES = 50000
MAP_NAMES = {'basecolor': 'BaseColor', 'normal': 'Normal', 'orm': 'ORM'}


def main(argv: list[str] | None = None) -> int:
    """Run the job file named after ``--`` on Blender's command line and write its result file.

    Args:
        argv: Full command line (defaults to ``sys.argv``); everything after ``--`` is ours.

    Returns:
        0 on success, 1 when the job failed (the result file then holds ``error`` and ``traceback``).
    """
    args = _job_args(sys.argv if argv is None else argv)
    if not args:
        print('usage: blender --background --python _blender_job.py -- job.json', file=sys.stderr)
        return 2
    job = json.loads(Path(args[0]).read_text(encoding='utf-8'))
    result_path = Path(job['result'])
    try:
        result = run(Path(job['source']), Path(job['output_dir']), OptimizeOptions.from_dict(job['options']))
        payload = result.to_dict()
        code = 0
    except Exception as err:  # pylint: disable=broad-exception-caught  # reported back to the host process
        payload = {'error': f'{type(err).__name__}: {err}', 'traceback': traceback.format_exc()}
        code = 1
    result_path.write_text(json.dumps(payload, indent=1), encoding='utf-8')
    return code


def run(source: Path, output_dir: Path, options: OptimizeOptions) -> OptimizeResult:
    """Optimize ``source`` into a game-ready mesh and textures in ``output_dir``.

    Args:
        source: Mesh file to optimize (see ``SOURCE_SUFFIXES``).
        output_dir: Directory for the outputs; created if missing.
        options: Pipeline settings.

    Returns:
        What was written, with measurements.

    Raises:
        OptimizeError: If the source has no mesh or cannot be imported.
    """
    name = options.name or source.stem
    output_dir.mkdir(parents=True, exist_ok=True)
    result = OptimizeResult(source=str(source), output_dir=str(output_dir))
    timings = result.timings

    with _timed(timings, 'import'):
        _reset_scene()
        hi = _import_source(source)
    diagonal = _diagonal(hi)
    result.stats['source'] = _mesh_stats(hi)
    result.stats['size'] = round(diagonal, 6)

    with _timed(timings, 'reduce'):
        low = _make_low(hi, name, options, diagonal)
    if result.stats['source']['tris'] <= options.target_tris:
        result.warnings.append(f'source has {result.stats["source"]["tris"]} triangles, already within the '
                               f'{options.target_tris} budget: kept, only re-unwrapped and re-baked')

    with _timed(timings, 'unwrap'):
        result.stats['uv'] = _unwrap(low, options)

    with _timed(timings, 'measure'):
        distances = _surface_distances(hi, low)
        result.stats['surface_error'] = _metrics.error_stats(distances, diagonal)
        game = _mesh_stats(low)
        game.update(_metrics.uv_metrics(**_mesh_arrays(low)))
        result.stats['game'] = game
    extrusion, ray = _metrics.bake_distances(float(np.nanmax(distances)) if distances.size else 0.0, diagonal)
    result.stats['bake'] = {'cage_extrusion': round(extrusion, 6), 'max_ray_distance': round(ray, 6),
                            'device': _configure_cycles(options)}

    with _timed(timings, 'bake'):
        images = _bake_maps(hi, low, name, options, extrusion, ray)
        _assign_game_material(low, name, images)
        result.textures = _save_textures(images, output_dir, name)

    with _timed(timings, 'export'):
        if options.export_glb:  # GLB embeds the OpenGL normal map glTF requires, so it goes first
            result.meshes.append(str(_export_glb(low, output_dir / f'{name}.glb')))
        if options.normal_convention == 'directx':
            _flip_normal_map(images['normal'], Path(result.textures['normal']))
        if options.export_fbx:
            result.meshes.append(str(_export_fbx(low, output_dir / f'{name}.fbx')))
        if options.keep_blend:
            result.blend = str(_save_blend(output_dir / f'{name}.blend'))

    report = output_dir / f'{name}_report.json'
    result.report = str(report)
    report.write_text(json.dumps(result.to_dict(), indent=1), encoding='utf-8')
    return result


# --- Internal (bpy functions only work inside Blender) ------------------------------

def _activate(obj) -> None:  # pragma: no cover - runs only inside Blender
    import bpy  # pylint: disable=import-outside-toplevel,import-error
    if bpy.context.object is not None and bpy.context.object.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    for other in bpy.context.view_layer.objects:
        other.select_set(other == obj)
    bpy.context.view_layer.objects.active = obj


def _assign_game_material(low, name: str, images: dict) -> None:  # pragma: no cover - runs only inside Blender
    """Replace the bake material with the final one: BaseColor, Normal, ORM (G roughness, B metallic)."""
    import bpy  # pylint: disable=import-outside-toplevel,import-error
    mat = bpy.data.materials.new(f'M_{name}')
    tree = mat.node_tree
    tree.nodes.clear()
    out = tree.nodes.new('ShaderNodeOutputMaterial')
    bsdf = tree.nodes.new('ShaderNodeBsdfPrincipled')
    tree.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    nodes = {}
    for i, key in enumerate(('basecolor', 'normal', 'orm')):
        node = tree.nodes.new('ShaderNodeTexImage')
        node.image = images[key]
        node.location = (-700, 300 - 300 * i)
        nodes[key] = node
    tree.links.new(nodes['basecolor'].outputs['Color'], bsdf.inputs['Base Color'])
    normal_map = tree.nodes.new('ShaderNodeNormalMap')
    tree.links.new(nodes['normal'].outputs['Color'], normal_map.inputs['Color'])
    tree.links.new(normal_map.outputs['Normal'], bsdf.inputs['Normal'])
    split = tree.nodes.new('ShaderNodeSeparateColor')
    tree.links.new(nodes['orm'].outputs['Color'], split.inputs['Color'])
    tree.links.new(split.outputs['Green'], bsdf.inputs['Roughness'])
    tree.links.new(split.outputs['Blue'], bsdf.inputs['Metallic'])
    low.data.materials.clear()
    low.data.materials.append(mat)


def _bake_maps(hi, low, name: str, options: OptimizeOptions, extrusion: float,
               ray: float) -> dict:  # pragma: no cover - runs only inside Blender
    """Bake BaseColor, Normal (OpenGL) and ORM from ``hi`` onto ``low``; return the Blender images."""
    import bpy  # pylint: disable=import-outside-toplevel,import-error
    bake = bpy.context.scene.render.bake
    bake.use_selected_to_active = True
    bake.cage_extrusion = extrusion
    bake.max_ray_distance = ray
    bake.margin = max(options.margin_px, 2)
    bake.margin_type = 'EXTEND'
    bake.normal_space = 'TANGENT'

    size = options.texture_size
    images = {}
    for key in ('basecolor', 'normal', 'orm'):
        image = bpy.data.images.new(f'T_{name}_{MAP_NAMES[key]}', size, size, alpha=False)
        if key != 'basecolor':
            image.colorspace_settings.name = 'Non-Color'
        images[key] = image

    mat = bpy.data.materials.new(f'M_{name}_bake')
    target = mat.node_tree.nodes.new('ShaderNodeTexImage')
    low.data.materials.clear()
    low.data.materials.append(mat)
    for obj in bpy.context.view_layer.objects:
        obj.select_set(obj in (hi, low))
    bpy.context.view_layer.objects.active = low

    for key, image in images.items():
        target.image = image
        mat.node_tree.nodes.active = target
        if key == 'normal':
            bpy.ops.object.bake(type='NORMAL')
            continue
        # Emission bakes copy the source values exactly; a diffuse bake would darken metals.
        restore = [_route_to_emission(m, key) for m in hi.data.materials if m is not None]
        try:
            bpy.ops.object.bake(type='EMIT')
        finally:
            for undo in restore:
                undo()
    return images


def _bpy():  # pragma: no cover - runs only inside Blender
    import bpy  # pylint: disable=import-outside-toplevel,import-error
    return bpy


def _configure_cycles(options: OptimizeOptions) -> str:  # pragma: no cover - runs only inside Blender
    """Set Cycles up for baking; return the device used (``'CPU'`` or e.g. ``'OPTIX'``)."""
    import bpy  # pylint: disable=import-outside-toplevel,import-error
    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = options.bake_samples
    scene.cycles.device = 'CPU'
    if not options.use_gpu:
        return 'CPU'
    prefs = bpy.context.preferences.addons['cycles'].preferences
    for backend in ('OPTIX', 'CUDA', 'HIP', 'METAL', 'ONEAPI'):
        try:
            prefs.compute_device_type = backend
        except TypeError:  # backend not built into this Blender
            continue
        prefs.get_devices()
        gpus = [d for d in prefs.devices if d.type == backend]
        if gpus:
            for device in prefs.devices:
                device.use = device.type == backend
            scene.cycles.device = 'GPU'
            return backend
    return 'CPU'


def _diagonal(obj) -> float:  # pragma: no cover - runs only inside Blender
    corners = np.array([obj.matrix_world @ _vector(c) for c in obj.bound_box])
    return float(np.linalg.norm(corners.max(axis=0) - corners.min(axis=0)))


def _edit_all(obj) -> None:  # pragma: no cover - runs only inside Blender
    import bpy  # pylint: disable=import-outside-toplevel,import-error
    _activate(obj)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type='FACE')
    bpy.ops.mesh.select_all(action='SELECT')


def _edit_faces(obj, faces: np.ndarray) -> None:  # pragma: no cover - runs only inside Blender
    """Enter edit mode on ``obj`` with exactly ``faces`` (bool per face) selected."""
    bpy = _bpy()
    _activate(obj)
    obj.data.polygons.foreach_set('select', np.asarray(faces, dtype=bool))
    obj.data.update()
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_mode(type='FACE')


def _export_fbx(low, path: Path) -> Path:  # pragma: no cover - runs only inside Blender
    import bpy  # pylint: disable=import-outside-toplevel,import-error
    _activate(low)
    bpy.ops.export_scene.fbx(filepath=str(path), use_selection=True, object_types={'MESH'},
                             apply_unit_scale=True, apply_scale_options='FBX_SCALE_NONE',
                             mesh_smooth_type='FACE', use_tspace=True, path_mode='RELATIVE',
                             add_leaf_bones=False, bake_anim=False)
    return path


def _export_glb(low, path: Path) -> Path:  # pragma: no cover - runs only inside Blender
    import bpy  # pylint: disable=import-outside-toplevel,import-error
    _activate(low)
    bpy.ops.export_scene.gltf(filepath=str(path), export_format='GLB', use_selection=True,
                              export_apply=True, export_yup=True, export_animations=False)
    return path


def _face_graph(obj) -> dict:  # pragma: no cover - runs only inside Blender
    """World positions, face normals/areas, corner indices and edge adjacency of ``obj``'s mesh."""
    mesh = obj.data
    matrix = np.array(obj.matrix_world)
    positions = np.empty(len(mesh.vertices) * 3)
    mesh.vertices.foreach_get('co', positions)
    positions = positions.reshape(-1, 3) @ matrix[:3, :3].T + matrix[:3, 3]
    normals = np.empty(len(mesh.polygons) * 3)
    mesh.polygons.foreach_get('normal', normals)
    normals = normals.reshape(-1, 3) @ matrix[:3, :3].T
    normals /= np.linalg.norm(normals, axis=1, keepdims=True) + 1e-20
    areas = np.empty(len(mesh.polygons))
    mesh.polygons.foreach_get('area', areas)
    starts = np.empty(len(mesh.polygons), dtype=np.int64)
    mesh.polygons.foreach_get('loop_start', starts)
    loop_vertices = np.empty(len(mesh.loops), dtype=np.int64)
    mesh.loops.foreach_get('vertex_index', loop_vertices)
    loop_edges = np.empty(len(mesh.loops), dtype=np.int64)
    mesh.loops.foreach_get('edge_index', loop_edges)
    loop_faces = np.repeat(np.arange(len(starts)), np.diff(np.append(starts, len(loop_vertices))))
    edge_vertices = np.empty(len(mesh.edges) * 2, dtype=np.int64)
    mesh.edges.foreach_get('vertices', edge_vertices)
    edge_vertices = edge_vertices.reshape(-1, 2)
    lengths = np.linalg.norm(positions[edge_vertices[:, 0]] - positions[edge_vertices[:, 1]], axis=1)
    return {'positions': positions, 'normals': normals, 'areas': areas, 'loop_vertices': loop_vertices,
            'loop_faces': loop_faces, 'edge_lengths': lengths,
            'edge_faces': _symmetry.edge_faces_from_loops(loop_edges, loop_faces, len(mesh.edges))}


def _flip_normal_map(image, path: Path) -> None:  # pragma: no cover - runs only inside Blender
    """Rewrite the saved normal map with the DirectX (Y-) green channel."""
    pixels = np.empty(len(image.pixels), dtype=np.float32)
    image.pixels.foreach_get(pixels)
    image.pixels.foreach_set(_metrics.flip_green(pixels))
    image.filepath_raw = str(path)
    image.save()


def _import_source(source: Path):  # pragma: no cover - runs only inside Blender
    """Import ``source`` and return one world-space mesh object holding all its meshes."""
    import bpy  # pylint: disable=import-outside-toplevel,import-error
    suffix = source.suffix.lower()
    path = str(source)
    if suffix in ('.usd', '.usda', '.usdc', '.usdz'):
        bpy.ops.wm.usd_import(filepath=path)
    elif suffix in ('.glb', '.gltf'):
        bpy.ops.import_scene.gltf(filepath=path)
    elif suffix == '.fbx':
        bpy.ops.import_scene.fbx(filepath=path)
    elif suffix == '.obj':
        bpy.ops.wm.obj_import(filepath=path)
    else:
        raise OptimizeError(f'unsupported source type {suffix!r}')
    meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH']
    if not meshes:
        raise OptimizeError(f'{source.name} contains no mesh')
    for obj in bpy.context.scene.objects:
        obj.hide_set(False)
        obj.hide_select = False
    for obj in bpy.context.view_layer.objects:
        obj.select_set(obj in meshes)
    bpy.context.view_layer.objects.active = meshes[0]
    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')
    bpy.ops.object.make_single_user(object=True, obdata=True)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    if len(meshes) > 1:
        bpy.ops.object.join()
    hi = bpy.context.view_layer.objects.active
    hi.name = 'source'
    return hi


def _job_args(argv: list[str]) -> list[str]:
    """Arguments after the first ``--`` (Blender's own arguments come before it)."""
    return argv[argv.index('--') + 1:] if '--' in argv else []


def _make_low(hi, name: str, options: OptimizeOptions, diagonal: float):  # pragma: no cover - inside Blender
    """Copy ``hi``, weld split vertices, collapse-decimate to the budget and shade smooth."""
    import bmesh  # pylint: disable=import-outside-toplevel,import-error
    import bpy  # pylint: disable=import-outside-toplevel,import-error
    low = hi.copy()
    low.data = hi.data.copy()
    low.name = low.data.name = name
    bpy.context.scene.collection.objects.link(low)

    mesh = low.data
    bm = bmesh.new()
    bm.from_mesh(mesh)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=options.merge_distance * diagonal)
    bm.to_mesh(mesh)
    bm.free()

    tris = _mesh_stats(low)['tris']
    if tris > options.target_tris:
        mod = low.modifiers.new('Decimate', 'DECIMATE')
        mod.ratio = options.target_tris / tris
        reduced = bpy.data.meshes.new_from_object(low.evaluated_get(bpy.context.evaluated_depsgraph_get()))
        low.modifiers.remove(mod)
        old, low.data = low.data, reduced
        bpy.data.meshes.remove(old)
        low.data.name = name
    mesh = low.data
    for attr in ('sharp_edge', 'sharp_face', 'custom_normal'):
        if attr in mesh.attributes:
            mesh.attributes.remove(mesh.attributes[attr])
    mesh.polygons.foreach_set('use_smooth', np.ones(len(mesh.polygons), dtype=bool))
    while mesh.uv_layers:
        mesh.uv_layers.remove(mesh.uv_layers[0])
    mesh.uv_layers.new(name='UVMap')
    mesh.update()
    return low


def _mesh_arrays(obj) -> dict:  # pragma: no cover - runs only inside Blender
    """Arrays for :func:`._metrics.uv_metrics` from ``obj``'s mesh and active UV map."""
    mesh = obj.data
    mesh.calc_loop_triangles()
    positions = np.empty(len(mesh.vertices) * 3)
    mesh.vertices.foreach_get('co', positions)
    loop_vertices = np.empty(len(mesh.loops), dtype=np.int64)
    mesh.loops.foreach_get('vertex_index', loop_vertices)
    uvs = np.empty(len(mesh.loops) * 2)
    mesh.uv_layers.active.uv.foreach_get('vector', uvs)
    starts = np.empty(len(mesh.polygons), dtype=np.int64)
    mesh.polygons.foreach_get('loop_start', starts)
    tris = np.empty(len(mesh.loop_triangles) * 3, dtype=np.int64)
    mesh.loop_triangles.foreach_get('loops', tris)
    return {'positions': positions.reshape(-1, 3), 'loop_vertices': loop_vertices,
            'loop_uvs': uvs.reshape(-1, 2), 'face_loop_starts': starts, 'tri_loops': tris.reshape(-1, 3)}


def _mesh_stats(obj) -> dict:  # pragma: no cover - runs only inside Blender
    mesh = obj.data
    mesh.calc_loop_triangles()
    return {'tris': len(mesh.loop_triangles), 'verts': len(mesh.vertices),
            'materials': len([m for m in mesh.materials if m is not None])}


def _nearest(points: np.ndarray):  # pragma: no cover - runs only inside Blender
    """A function returning the distance from each query point to the nearest of ``points``."""
    from mathutils.kdtree import KDTree  # pylint: disable=import-outside-toplevel,import-error
    tree = KDTree(len(points))
    for index, point in enumerate(points):
        tree.insert(point, index)
    tree.balance()
    return lambda query: np.array([tree.find(q)[2] for q in query])


def _proxy_seams(low, options: OptimizeOptions, faces: np.ndarray) -> np.ndarray:  # pragma: no cover
    """Seams Smart UV Project finds for ``faces`` (bool per face) on a smoothed copy of ``low``.

    Runs only inside Blender. Smoothing removes the surface noise of generated meshes that otherwise
    splits the UVs into thousands of islands.
    """
    seams = np.zeros(len(low.data.edges), dtype=bool)
    if not np.any(faces):
        return seams
    bpy = _bpy()
    proxy = low.copy()
    proxy.data = low.data.copy()
    bpy.context.scene.collection.objects.link(proxy)
    _smooth_mesh(proxy.data, options.seam_smooth_iterations)
    _edit_faces(proxy, faces)
    bpy.ops.uv.smart_project(angle_limit=math.radians(options.seam_angle), island_margin=options.margin_fraction,
                             area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.uv.seams_from_islands(mark_seams=True, mark_sharp=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    proxy.data.edges.foreach_get('use_seam', seams)
    proxy_mesh = proxy.data
    bpy.data.objects.remove(proxy)
    bpy.data.meshes.remove(proxy_mesh)
    return seams


def _reset_scene() -> None:  # pragma: no cover - runs only inside Blender
    import bpy  # pylint: disable=import-outside-toplevel,import-error
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.scene.tool_settings.use_uv_select_sync = True


def _route_to_emission(mat, key: str):  # pragma: no cover - runs only inside Blender
    """Temporarily drive ``mat``'s output with an emission of its albedo (``basecolor``) or of
    (1, roughness, metallic) (``orm``). Returns a function that restores the material."""
    tree = mat.node_tree
    out = next((n for n in tree.nodes if n.type == 'OUTPUT_MATERIAL' and n.is_active_output), None) \
        or next((n for n in tree.nodes if n.type == 'OUTPUT_MATERIAL'), None) \
        or tree.nodes.new('ShaderNodeOutputMaterial')
    surface = out.inputs['Surface']
    previous = surface.links[0].from_socket if surface.links else None
    bsdf = next((n for n in tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    added = [tree.nodes.new('ShaderNodeEmission')]
    emission = added[0]

    def feed(socket_name: str, target) -> None:
        """Link the BSDF input (or copy its value) into ``target``."""
        if bsdf is None:
            fallback = {'Base Color': tuple(mat.diffuse_color), 'Roughness': mat.roughness,
                        'Metallic': mat.metallic}[socket_name]
            target.default_value = fallback
            return
        source = bsdf.inputs[socket_name]
        if source.links:
            tree.links.new(source.links[0].from_socket, target)
        else:
            target.default_value = source.default_value

    if key == 'basecolor':
        feed('Base Color', emission.inputs['Color'])
    else:
        combine = tree.nodes.new('ShaderNodeCombineColor')
        added.append(combine)
        combine.inputs['Red'].default_value = 1.0
        feed('Roughness', combine.inputs['Green'])
        feed('Metallic', combine.inputs['Blue'])
        tree.links.new(combine.outputs['Color'], emission.inputs['Color'])
    tree.links.new(emission.outputs['Emission'], surface)

    def restore() -> None:
        for node in added:
            tree.nodes.remove(node)
        if previous is not None:
            tree.links.new(previous, surface)
    return restore


def _save_blend(path: Path) -> Path:  # pragma: no cover - runs only inside Blender
    import bpy  # pylint: disable=import-outside-toplevel,import-error
    bpy.ops.wm.save_as_mainfile(filepath=str(path), copy=True)
    return path


def _save_textures(images: dict, output_dir: Path, name: str) -> dict[str, str]:  # pragma: no cover
    """Save each baked image as PNG; return their paths. (Runs only inside Blender.)"""
    paths = {}
    for key, image in images.items():
        path = _texture_path(output_dir, name, key)
        image.filepath_raw = str(path)
        image.file_format = 'PNG'
        image.save()
        paths[key] = str(path)
    return paths


def _smooth_mesh(mesh, iterations: int) -> None:  # pragma: no cover - runs only inside Blender
    import bmesh  # pylint: disable=import-outside-toplevel,import-error
    bm = bmesh.new()
    bm.from_mesh(mesh)
    for _ in range(iterations):
        bmesh.ops.smooth_vert(bm, verts=bm.verts, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    bm.to_mesh(mesh)
    bm.free()


def _smoothed_face_normals(obj, iterations: int) -> np.ndarray:  # pragma: no cover - runs only inside Blender
    """World-space face normals of a smoothed copy of ``obj``'s mesh: the overall form, without noise."""
    mesh = obj.data.copy()
    _smooth_mesh(mesh, iterations)
    normals = np.empty(len(mesh.polygons) * 3)
    mesh.polygons.foreach_get('normal', normals)
    _bpy().data.meshes.remove(mesh)
    normals = normals.reshape(-1, 3) @ np.array(obj.matrix_world)[:3, :3].T
    return normals / (np.linalg.norm(normals, axis=1, keepdims=True) + 1e-20)


def _surface_distances(hi, low) -> np.ndarray:  # pragma: no cover - runs only inside Blender
    """Distance from sampled source vertices to the game mesh, plus from every game vertex to the source."""
    import bpy  # pylint: disable=import-outside-toplevel,import-error
    from mathutils.bvhtree import BVHTree  # pylint: disable=import-outside-toplevel,import-error
    depsgraph = bpy.context.evaluated_depsgraph_get()
    tree_low = BVHTree.FromObject(low, depsgraph)
    tree_hi = BVHTree.FromObject(hi, depsgraph)
    verts = hi.data.vertices
    picks = np.random.default_rng(0).choice(len(verts), min(ERROR_SAMPLES, len(verts)), replace=False)
    out = [tree_low.find_nearest(verts[int(i)].co)[3] for i in picks]
    out += [tree_hi.find_nearest(v.co)[3] for v in low.data.vertices]
    return np.array([np.nan if d is None else d for d in out], dtype=np.float64)


def _texture_path(output_dir: Path, name: str, key: str) -> Path:
    return output_dir / f'T_{name}_{MAP_NAMES[key]}.png'


@contextmanager
def _timed(timings: dict[str, float], step: str):
    start = time.perf_counter()
    try:
        yield
    finally:
        timings[step] = round(time.perf_counter() - start, 2)


def _unwrap(low, options: OptimizeOptions) -> dict:  # pragma: no cover - runs only inside Blender
    """Unwrap and pack ``low``, choosing the method from ``options.uv_method``.

    Flat assets get an artist-style layout: the mid-plane is found, the faces turned to the front and back
    are planar-projected (the back mirrored) and only the side walls are unwrapped. Other shapes get seams
    from a smoothed copy, where Smart UV Project finds islands without the surface noise of generated
    meshes. Either way, slivers are merged into their neighbours before the angle-based unwrap and packing.

    Returns:
        Report: the method used and, unless ``seams`` was requested, the plane fit and projected share.
    """
    bpy = _bpy()
    graph = _face_graph(low)
    labels = np.zeros(len(graph['areas']), dtype=np.int64)
    report: dict = {'requested': options.uv_method}
    normal = None
    if options.uv_method != 'seams':
        normal, _, error = _symmetry.symmetry_plane(graph['positions'], _nearest(graph['positions']))
        smooth_normals = _smoothed_face_normals(low, options.seam_smooth_iterations)
        labels = _symmetry.classify_faces(smooth_normals @ normal, graph['normals'] @ normal, graph['areas'],
                                          graph['edge_faces'])
        share = _symmetry.projected_share(labels, graph['areas'])
        report.update(mirror_error_pct=round(error * 100, 3), projected_pct=round(share * 100, 1))
    report['method'] = _symmetry.choose_uv_method(options.uv_method, report.get('projected_pct', 0.0) / 100)
    if report['method'] == 'seams':
        labels[:] = _symmetry.SIDE

    side_seams = _proxy_seams(low, options, labels == _symmetry.SIDE)
    labels, side_seams = _symmetry.merge_small_islands(labels, side_seams, graph['edge_faces'],
                                                       graph['edge_lengths'])
    mesh = low.data
    mesh.edges.foreach_set('use_seam', _symmetry.final_seams(labels, side_seams, graph['edge_faces']))
    if report['method'] == 'symmetry':
        axis_a, axis_b = _symmetry.in_plane_basis(graph['positions'], normal)
        uvs = _symmetry.planar_uvs(graph['positions'][graph['loop_vertices']], labels[graph['loop_faces']],
                                   axis_a, axis_b)
        mesh.uv_layers.active.uv.foreach_set('vector', uvs.ravel())
    mesh.update()
    report['faces'] = {'front': int((labels == _symmetry.FRONT).sum()),
                       'back': int((labels == _symmetry.BACK).sum()),
                       'side': int((labels == _symmetry.SIDE).sum())}

    margin = options.margin_fraction
    side = labels == _symmetry.SIDE
    if side.any():
        _edit_faces(low, side)
        bpy.ops.uv.unwrap(method='ANGLE_BASED', fill_holes=True, correct_aspect=True,
                          margin_method='FRACTION', margin=margin)
        bpy.ops.object.mode_set(mode='OBJECT')
    _edit_all(low)
    bpy.context.scene.tool_settings.use_uv_select_sync = True
    bpy.ops.uv.average_islands_scale()
    bpy.ops.uv.pack_islands(udim_source='CLOSEST_UDIM', rotate=True, rotate_method='ANY', scale=True,
                            merge_overlap=False, margin_method='FRACTION', margin=margin, shape_method='CONCAVE')
    bpy.ops.object.mode_set(mode='OBJECT')
    return report


def _vector(values):  # pragma: no cover - runs only inside Blender
    from mathutils import Vector  # pylint: disable=import-outside-toplevel,import-error
    return Vector(values)


if __name__ == '__main__':
    sys.exit(main())
