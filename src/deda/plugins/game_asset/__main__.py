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
"""Command line and standalone window for the game asset optimizer.

Run with:
    python -m deda.plugins.game_asset                          # open the window
    python -m deda.plugins.game_asset axe.usdz                 # writes axe_game/ next to the input
    python -m deda.plugins.game_asset axe.usdz -o out --tris 8000 --texture-size 1024 --directx-normals
    python -m deda.plugins.game_asset a.usdz b.glb -o out      # one sub-directory per input
"""
import argparse
import logging
import sys
from pathlib import Path

from ._options import NORMAL_CONVENTIONS, TEXTURE_SIZES, UV_METHODS, OptimizeError, OptimizeOptions
from ._runner import default_output_dir, optimize

log = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> int:
    """Optimize the mesh files named in ``argv``, or open the window when there are none.

    Args:
        argv: Command line arguments (defaults to ``sys.argv[1:]``).

    Returns:
        Process exit code: 0 on success, 1 if any input failed, 2 on bad arguments.
    """
    args = _build_parser().parse_args(argv)
    if not args.inputs:
        return _run_window()
    options = OptimizeOptions(target_tris=args.tris, texture_size=args.texture_size,
                              normal_convention=args.normals, margin_px=args.margin, uv_method=args.uv,
                              use_gpu=not args.cpu, export_fbx=not args.no_fbx, export_glb=not args.no_glb,
                              keep_blend=args.keep_blend)
    try:
        options.validate()
    except OptimizeError as err:
        print(f'error: {err}', file=sys.stderr)
        return 2
    return _run_cli(args.inputs, args.output, options, args.blender, args.verbose)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog='python -m deda.plugins.game_asset',
                                     description='Reduce, unwrap and bake dense meshes into game-ready assets '
                                                 '(runs Blender in the background).')
    parser.add_argument('inputs', nargs='*', type=Path, help='mesh files (none: open the window)')
    parser.add_argument('-o', '--output', type=Path,
                        help='output directory (several inputs: one sub-directory each)')
    parser.add_argument('--tris', type=int, default=OptimizeOptions.target_tris, help='triangle budget')
    parser.add_argument('--texture-size', type=int, default=OptimizeOptions.texture_size, choices=TEXTURE_SIZES)
    parser.add_argument('--normals', choices=NORMAL_CONVENTIONS, default=OptimizeOptions.normal_convention,
                        help='normal map convention of the PNG (GLB is always OpenGL); directx for Unreal')
    parser.add_argument('--margin', type=int, default=OptimizeOptions.margin_px, help='UV padding in pixels')
    parser.add_argument('--uv', choices=UV_METHODS, default=OptimizeOptions.uv_method,
                        help='symmetry: planar projection of each side of a flat asset; seams: for round shapes; '
                             'auto: symmetry when the front and back cover most of the surface')
    parser.add_argument('--cpu', action='store_true', help='bake on the CPU even when a GPU is available')
    parser.add_argument('--no-fbx', action='store_true', help='do not write the FBX')
    parser.add_argument('--no-glb', action='store_true', help='do not write the GLB')
    parser.add_argument('--keep-blend', action='store_true', help='also save the working .blend')
    parser.add_argument('--blender', type=Path, help='Blender executable (default: auto-detect)')
    parser.add_argument('-v', '--verbose', action='store_true', help="print Blender's output")
    return parser


def _output_for(source: Path, output: Path | None, count: int) -> Path:
    """``output`` itself for one input, ``output/<stem>`` for several, or the default next to the input."""
    if output is None:
        return default_output_dir(source)
    return output if count == 1 else output / source.stem


def _run_cli(inputs: list[Path], output: Path | None, options: OptimizeOptions, blender: Path | None,
             verbose: bool) -> int:
    failures = 0
    for source in inputs:
        destination = _output_for(source, output, len(inputs))
        print(f'{source} -> {destination}')
        try:
            result = optimize(source, destination, options, blender=blender,
                              on_output=print if verbose else None)
        except OptimizeError as err:
            print(f'FAILED {source}: {err}', file=sys.stderr)
            failures += 1
            continue
        print(f'  {result.summary()}')
        for path in result.meshes + list(result.textures.values()):
            print(f'  wrote {path}')
        for warning in result.warnings:
            print(f'  warning: {warning}')
    return 1 if failures else 0


def _run_window() -> int:  # pragma: no cover - starts the Qt event loop
    from PySide6 import QtWidgets  # pylint: disable=import-outside-toplevel
    from ._tool_window import GameAssetWindow  # pylint: disable=import-outside-toplevel
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    window = GameAssetWindow()
    window.show()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
