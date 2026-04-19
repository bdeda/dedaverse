---
title: Short imperative title (overrides the first H1 below)
template: default
status: Open
priority: normal
---

# Short imperative title

Describe the task here in plain Markdown. Everything below the closing
`---` fence is appended to the prompt template and sent to Copilot as the
task body, so write it the way you'd brief a capable engineer who has
full repo access but no prior context:

- What the goal is and why it matters.
- Any constraints, preferred approach, or files to focus on.
- What "done" looks like (tests pass, a PR opened, a file produced).

## Attachments

Drop supporting files next to this `task.md` in the same task directory
(e.g. `task1/ref.png`, `task1/spec.md`). They are surfaced to the runner
as absolute paths via `Task.metadata['attachments']` — reference them by
filename in the body if the prompt should read them.

## Front-matter fields

- `title` — promoted onto `Task.title`. Optional; falls back to the first
  `# H1` line, then to the directory name.
- `template` — name of the prompt template under `templates/` (without
  `.md`). Optional; defaults to `default`.
- `status` — one of `Open`, `In-Progress`, `Blocked`, `Ready-for-Review`,
  `Closed`, `Resolved`. Case- and separator-insensitive (`open`, `ready
  for review`, `ready_for_review` all parse). Defaults to `Open`. Only
  `Open` tasks are dispatched; edit the file to change state.
- Any other `key: value` pairs are preserved on `Task.metadata` for
  readiness policies (priority, due date, dependencies, etc.) — schema
  is intentionally open while the policy layer is still a stub.

## Usage

Copy this file into a new numbered directory under the tasks root:

    ~/.dedaverse/operation/tasks/task<N>/task.md

Where `<N>` is the next available integer (tasks are sorted numerically,
so `task1`, `task2`, ..., `task10`, `task11` all order as expected).
