# Asset Metadata and Directory Design

This document describes the directory structure and USD metadata layout for asset metadata stored under the `.dedaverse` subfolder of a project, and how that design is mirrored for asset content (art) directories. **Keep agentic and manual code changes aligned with this design.**

## Overview

- **Metadata** lives under `{project_root}/.dedaverse/`. It uses USDA files and USD composition (sublayers) to represent the asset hierarchy.
- **Asset content** (art files: USD, textures, etc.) lives under the project root in directories that **mirror the USD prim path** of each asset/collection. Metadata is *not* stored in these content directories.

## 1. Metadata: `.dedaverse` Directory Structure

### 1.1 Top Level

```
{project_root}/
└── .dedaverse/
    ├── {project_name}.usda          # Project stage (single root USDA; project_name from project config)
    ├── user_settings.usda           # Session layer: user overrides and user-facing metadata
    ├── {CollectionA}.usda         # Collection directly under project (e.g. Sequences, Assets)
    ├── {CollectionA}/             # Child metadata dir for CollectionA
    │   ├── {AssetB}.usda         # Asset or collection under CollectionA
    │   ├── {CollectionC}.usda
    │   └── {CollectionC}/        # Child metadata dir for CollectionC
    │       └── {AssetD}.usda
    └── ...
```

Rules:

- **Project**: One USDA file at `.dedaverse/{project_name}.usda`. The project stage has **no root prim**; the root layer only has `subLayerPaths` pointing to child USDA files. `project_name` comes from project config (e.g. `KCIRC`). A second file `.dedaverse/user_settings.usda` is created alongside it and loaded as the stage’s **session layer** for user overrides and user-facing metadata; it is saved whenever it is edited.
- **Collection under project**: One USDA at `.dedaverse/{collection_name}.usda`. Its **children** are described by USDA files under `.dedaverse/{collection_name}/{name}.usda` (sublayers).
- **Asset or collection under a collection**: USDA at `.dedaverse/{ParentName}/{ChildName}.usda` (or deeper for nested parents). The **parent’s** layer lists this file in `subLayerPaths` (path relative to the parent layer’s directory).

### 1.2 Path Rules (Metadata)

| Entity            | `metadata_path` (USDA file)                    | `children_metadata_dir` (dir for child USDA files) |
|-------------------|------------------------------------------------|-----------------------------------------------------|
| Project           | `.dedaverse/{project_name}.usda`                  | `.dedaverse`                                        |
| Collection (root) | `.dedaverse/{collection_name}.usda`             | `.dedaverse/{collection_name}`                       |
| Asset/Collection  | `parent.children_metadata_dir / {name}.usda`   | `parent.children_metadata_dir / {name}`             |

So:

- Project’s children USDA files live in `.dedaverse/` (same as metadata dir).
- A collection’s children USDA files live in a subfolder named after that collection: `.dedaverse/{collection_name}/`.
- An asset’s USDA file lives in its parent’s `children_metadata_dir`; assets do not have a `children_metadata_dir` used for further USDA (only collections do).

## 2. USD Metadata File Structure

### 2.1 Project Stage (`.dedaverse/{project_name}.usda`) and Session Layer (`user_settings.usda`)

- **Root layer**: No root prim. The layer only contains `subLayerPaths` (e.g. `["Sequences.usda", "Assets.usda"]`). Child prims (e.g. `/Sequences`, `/Assets`) are composed from those sublayers.
- **Session layer**: `.dedaverse/user_settings.usda` is created whenever the project USDA is created and is loaded as the project `Usd.Stage`’s session layer. User overrides and user-facing metadata applied to the asset library are stored here. The session layer must be saved whenever it is edited (e.g. via `Project.save_session_layer()`). **Collection sort order**: for each collection prim, the session layer can hold an override with custom metadata `sort_order` (a list of child names in display order). This is used by the Assets panel to show and persist the user’s chosen order for that collection’s immediate children (`Project.get_collection_sort_order` / `set_collection_sort_order`).
- The project’s `Usd.Stage` is opened on the root layer; the session layer is attached so that session edits compose over the root and sublayers.

### 2.2 Collection or Asset USDA (child USDA files)

- **Root prims**: The USDA contains a **prim for every level** of the hierarchy from the root scope down to the new entity. For a **child under the project**, that is a single root prim (e.g. `/Sequences`). For a **nested child**, the file includes the full chain (e.g. `/Sequences/INTRO/Scene_01` with prims at each level).
- **Prim types**: All are `Scope`. Kinds are set via `Usd.ModelAPI`:
  - **Collection (group)**: `Kind.Tokens.group` on the leaf; ancestor scopes also get `group`.
  - **Asset (model)**: `Kind.Tokens.model` on the leaf; ancestors get `group`.
- **Asset identity**: For assets (not collections), the leaf prim gets `assetInfo` (e.g. `SetAssetName`, `SetAssetIdentifier`). The identifier format is `project_name:collection_name:...:asset_name::`.
- **Default prim**: Set to the leaf prim of the hierarchy in that file.
- **Sublayers**: A collection’s (or project’s) layer lists its children in `subLayerPaths`. Paths are **relative to the directory containing that layer**. Example: from `.dedaverse/KCIRC.usda`, a sublayer might be `Sequences/INTRO.usda`; from `.dedaverse/Sequences.usda`, a sublayer might be `INTRO.usda` (under `.dedaverse/Sequences/`).

### 2.3 Creating or Overwriting a Child USDA

- If the USDA path **does not exist**: create with `Usd.Stage.CreateNew(path)` and write the scope hierarchy and kind/assetInfo.
- If the USDA path **already exists** (e.g. re-creating an asset after remove): open with `Usd.Stage.Open(path)`, **remove all root prims**, then write the same hierarchy and save. This avoids “layer already exists” errors when reusing the same name.

## 3. Asset Content Directories (Mirror of Prim Path)

Art files (USD scenes, textures, etc.) are **not** stored under `.dedaverse`. They live under the project root in directories that **mirror the USD prim path** of each asset or collection.

### 3.1 Mapping: Prim Path → Content Directory

- **Prim path** on the project stage: e.g. `/Sequences`, `/Sequences/INTRO`, `/Assets/Monsters/Cletus`.
- **Content directory**: `{project_root}/{path_without_leading_slash}`.

So:

- `/Sequences`           → `{project_root}/Sequences/`
- `/Sequences/INTRO`     → `{project_root}/Sequences/INTRO/`
- `/Assets/Monsters/Cletus` → `{project_root}/Assets/Monsters/Cletus/`

Implementation: `Project.asset_directory_for_prim_path(prim_path)` returns `rootdir.joinpath(*segments)` where `segments` is `prim_path.strip("/").split("/")`.

### 3.2 Content Directory Layout (Convention)

- Each asset’s **content root** is `asset.rootdir` (= `project.asset_directory_for_prim_path(asset.prim_path)`).
- Typical use: place the main USD file (e.g. `{AssetName}.usd` or `{AssetName}.usda`) and related art (textures, caches) under that directory.
- **Archive**: When an asset/collection is removed from the hierarchy, the UI may move existing contents of that content directory into an `archive/` subfolder under the same path (e.g. `Sequences/INTRO/archive/`) instead of deleting them. The `.dedaverse` metadata file for that child is **not** deleted on remove; only the sublayer reference is removed from the parent. Re-creating an asset with the same name reuses or overwrites that USDA as in §2.3.

### 3.3 Summary Table

| Prim path              | Metadata (USDA)                      | Content directory (art)        |
|------------------------|--------------------------------------|--------------------------------|
| (project)              | `.dedaverse/{project_name}.usda`        | (project root)                 |
| `/Sequences`           | `.dedaverse/Sequences.usda`          | `{project_root}/Sequences/`     |
| `/Sequences/INTRO`     | `.dedaverse/Sequences/INTRO.usda`    | `{project_root}/Sequences/INTRO/` |
| `/Assets/Monsters/Cletus` | `.dedaverse/Assets/Monsters/Cletus.usda` | `{project_root}/Assets/Monsters/Cletus/` |

So: **metadata path under `.dedaverse`** and **content path under project root** both follow the same logical hierarchy (prim path); metadata uses `.dedaverse` and per-entity USDA files, while content uses plain directories under the project root.

## 4. References in Code

- **Project**: `src/deda/core/types/_project.py` — `metadata_dir`, `metadata_path`, `user_settings_path`, `children_metadata_dir`, `asset_directory_for_prim_path`, `stage` (root + session layer), `save_session_layer()`, stage creation.
- **Collection / Asset**: `src/deda/core/types/_asset.py`, `_collection.py` — `metadata_path`, `children_metadata_dir`, `rootdir` (content), `add_asset` / `add_collection`, `remove_child`, `_create_entity_usda`, sublayer add/remove.
- **Entity base**: `src/deda/core/types/_entity.py` — `prim_path`, resolution from path.

When changing hierarchy, USDA layout, or content paths, update this document and keep implementation in sync with the rules above.
