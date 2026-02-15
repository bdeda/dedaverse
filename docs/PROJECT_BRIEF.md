# Dedaverse — Project Brief

## Vision

Dedaverse is an **asset management system for visual media projects** (films, games, and related productions). It helps teams track and version assets from concept to delivery while keeping artists focused on creative work and producers on status and cost.

## Goals

- **Art-first workflow** — Answer quickly: what’s planned, in progress, done today, and what changed.
- **Production visibility** — Track development time and cost by asset and element so producers can report accurately.
- **Technical flexibility** — Support different studios via plugins for version control, task tracking, and DCC tools without locking users into one pipeline.

## Target Users

- **Artists** — Browse assets, open them in DCC apps, and iterate without dealing with low-level version control or path details.
- **Producers / project managers** — See status, progress, and cost by asset or element.
- **Technical directors / pipeline** — Configure projects, plugins, and integrations (Perforce, Jira, DCC launchers) to match studio needs.

## Core Capabilities

- **Project and asset hierarchy** — Projects contain collections and assets in a tree; metadata is stored under a project’s `.dedaverse` directory using USDA (USD ASCII) and composition (references, session layer).
- **Metadata and references** — Asset and collection metadata (names, types, descriptions, custom data) live in USDA; optional linkage to task systems (e.g. Jira) and to versioned art files.
- **Desktop application** — PySide6-based UI: project selector, panels for Assets / Apps / Services, asset browser, notes and annotations, optional USD viewer with camera reticle and slate overlay.
- **Viewer** — Built-in USD viewer for inspecting scenes and adding slates/annotations; camera reticle with safe zones; playbar and basic view controls.
- **Plugins** — Plugin system for Application (DCC launchers, e.g. Maya, Houdini), FileManager (e.g. Perforce, local), TaskManager (e.g. Jira), and other extension points; plugins are discoverable and configurable.
- **Configuration** — Layered config: site, user, and project; project root and prim name drive where `.dedaverse` and USDA live.

## Technology

- **Language / runtime** — Python 3.12+.
- **UI** — PySide6 (Qt for Python).
- **Asset metadata** — USD Core (usd-core); USDA files and composition for hierarchy and user overrides (e.g. sort order in `user_settings.usda` session layer).
- **Integrations** — p4python (Perforce), requests, dataclasses_json; Click CLI; optional dependencies for plugins (e.g. Jira, DCC finders/launchers).
- **Delivery** — Installable package (`dedaverse`); CLI entry point; optional system-tray and startup install for desktop use.

## Current Status

- **Phase** — Active development (WIP). Core app, project/collection/asset model, USDA layout, viewer, and key plugins (e.g. Perforce, app launchers) exist; some areas are still being refined (e.g. asset metadata layout, CI/Codecov).
- **Platform** — Primary development on Windows; CI (e.g. GitHub Actions) runs tests on Linux with headless Qt/USD; cross-platform compatibility is a goal.
- **Documentation** — README (getting started, focus on art/production/tech), AGENTS.md (contributor and AI-agent guidance), ASSET_METADATA_DESIGN.md (metadata and directory design), and this brief.

## Success Criteria (High Level)

- Artists can open the app, pick a project, and work with assets and DCCs without editing config files.
- Producers can see status and cost-related information derived from asset and task data.
- Pipeline can add or adjust plugins and project settings so Dedaverse fits existing version control and task management.

---

*Last updated: 2026-02*
