# Viewer: 2D media and Dedacam

`python -m deda.core.viewer [path]` opens a USD stage in the 3D viewport, or an image, an
image sequence or a video in the 2D viewport. File > Open, drag and drop, the recent files list
and the command line all take either kind of file.

## 2D images, sequences and video

- **Images**: PNG, JPEG, TIFF (8 and 16 bit), BMP, WebP, TGA, GIF through Qt, and **EXR** (float,
  linear, shown through the sRGB curve) when the `OpenEXR` package is installed:
  `pip install -e ".[media]"`.
- **Sequences**: open any one frame (`shot.0001.exr`) and the rest are found: `shot.0001.png`,
  `shot_0001.png`, `shot.1001.exr`, unpadded `a1.png` ... `a10.png`. A pattern such as
  `shot.####.exr` or `shot.%04d.exr` works from the command line. Missing frames hold the previous
  frame, and the info overlay says how many are missing.
- **Video**: MP4, MOV, M4V, AVI, MKV, WebM, WMV through `QtMultimedia`. Scrubbing seeks to the
  frame; playing streams at the video's own frame rate (audio is not played).
- **Controls**: the playbar scrubs and plays. Wheel zooms around the cursor, drag pans, double-click
  or `F` fits, View > Actual Size (`Ctrl+Shift+1`) shows 100%. View > 2D Channels (`Ctrl+1` to
  `Ctrl+6`) shows RGBA, RGB, or one channel; `Ctrl+Up`/`Ctrl+Down` change exposure by a stop and
  `Ctrl+0` resets it. The info overlay shows the file, size, frame and the value under the cursor.

## Dedacam in the 3D viewport

View > Dedacam turns on Dedacam's camera effects for the viewport: **Depth of Field**, **Focus
Zones** and **Depth**, at a chosen quality tier. It reuses Dedacam's usdview plugin, which hooks the
viewer's `StageView`.

1. Build the plugin from the dedacam repository against the **same USD the viewer runs on**:
   `-DDEDACAM_BUILD_USDVIEW=ON -DDEDACAM_USD_ROOT=<usd install>` (see its `hosts/usdview/README.md`).
2. Set `DEDACAM_BUILD_DIR` to that build directory (the one that contains `usdview/` and `python/`).
3. Look through a stage camera with View > Camera. The free camera has no lens or focus settings,
   so nothing is out of focus. Lens, T-stop and focus distance come from the camera prim (and
   `dedacam:` attributes on it).

Depth of field needs a GPU with OpenGL and runs on the viewer's own render, so the viewer's locked
aspect ratio (letterbox) is respected.
