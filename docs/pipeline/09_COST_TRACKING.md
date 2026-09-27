# 9. Cost Tracking

The Director must be able to ask the Producer *"What has asset X cost to build?"* and get an accurate, auditable
answer. This document defines how every cost is recorded when it is incurred, where the records live, and how the
Producer turns them into a report.

Accuracy comes from three rules:

1. **Record at the source, when the cost is incurred.** Costs are never reconstructed from memory or estimated
   after the fact. The agent or process that incurs a cost writes the record.
2. **Measure, don't guess.** Every quantity comes from a measurement: token counts reported by the model
   runtime, job logs, review session timestamps, invoices. Anything that is not measured is labeled as an
   estimate and reported separately.
3. **Every number is traceable.** Each record carries its raw quantity, the rate used, the source of the
   measurement, and the asset, element, task, and role it belongs to. A total can always be broken back down into
   the records that produced it.

> This is a process specification. Dedaverse does not yet provide an API for the ledger; agents read and write the
> ledger files directly using the format below.

---

## 9.1 What counts as cost

| Category | What it covers | Raw quantity | Measurement source |
|----------|----------------|--------------|--------------------|
| `agent_usage` | Model usage by every agent working on the asset, including the Producer's work for that asset | Model ID; input, output, cache-write, and cache-read tokens | Usage reported by the model runtime or API response for each request or session |
| `compute` | Rendering, simulation, baking, capture solving, and other machine time | Machine or resource type; hours | Job logs (start/end time, resource) from the render farm, scheduler, or local job runner |
| `director_time` | The Director's time reviewing and directing work on the asset | Hours | Review session start/end timestamps recorded by the Producer and confirmed by the Director |
| `external` | Money paid to outside parties: voice actors, mocap sessions, licensed music, stock assets, software seats, outsourcing | Amount, currency, vendor | Invoice or receipt, with its reference number |

---

## 9.2 Where records live

The **project ledger** is the source of truth. When the Jira task manager plugin is configured, the Producer also
mirrors the records to Jira (see [9.6](#96-mirroring-to-jira)).

```
{project_root}/.dedaverse/cost-ledger/
├── rates.json                         # Currency and rates, versioned with effective dates
├── tasks/
│   └── {task_id}.jsonl                # Records for one task (agent usage, compute), written by the assigned role agent
├── director/
│   └── {YYYY-MM}.jsonl                # Director review time, written by the Producer
└── external/
    └── {YYYY-MM}.jsonl                # External spend, written by the Producer
```

- **Name.** The directory is `cost-ledger` because a hyphen is not valid in a USD prim name, so it cannot
  collide with a collection's metadata directory under `.dedaverse/`.
- **Append only.** Records are never edited or deleted. Mistakes are fixed with a correction record
  (see [9.4](#94-corrections)).
- **One writer per file.** Each task file is written only by the agent assigned to that task. The `director/`
  and `external/` files are written only by the Producer. This avoids merge conflicts and exclusive-checkout
  collisions in the file manager (e.g. Perforce).
- **Versioned.** Ledger files are submitted through the project's configured file manager plugin, like any other
  project file, at least at every task submission.

---

## 9.3 Record format

Each line in a ledger file is one JSON object:

```json
{
  "id": "0b6f1c1e-6a53-4c9e-9d58-3f1b8f0f2a71",
  "timestamp": "2026-09-27T19:25:11Z",
  "asset_id": "KCIRC:Assets:Characters:Hero::",
  "prim_path": "/Assets/Characters/Hero",
  "element": "rig",
  "task_id": "KCIRC-142",
  "role": "rigger",
  "category": "agent_usage",
  "quantity": {
    "model": "<model id>",
    "input_tokens": 182340,
    "output_tokens": 24110,
    "cache_write_tokens": 0,
    "cache_read_tokens": 90112
  },
  "rates_version": 3,
  "amount": 1.87,
  "currency": "USD",
  "measured": true,
  "source": "runtime-usage",
  "rework": false,
  "rework_reason": null,
  "corrects": null,
  "recorded_by": "rigger",
  "note": "Pose-target iteration 4"
}
```

| Field | Rule |
|-------|------|
| `id` | Unique ID (UUID) for the record. |
| `timestamp` | UTC, ISO 8601, when the cost was incurred (end of the session or job). |
| `asset_id` | The Dedaverse asset ID of the asset or shot (format `project:collection:...:asset::`). Shared work uses the ID of its own collection, e.g. `KCIRC:Reference:VisualBible::`. |
| `prim_path` | The entity's prim path, for readability and cross-checking. |
| `element` | The element folder name the work belongs to (`concept`, `model`, `textures`, `rig`, `anim`, ...). |
| `task_id` | The task the cost was incurred for. Every record has one. |
| `role` | The role skill that incurred the cost (`director` for Director time). |
| `category` | One of `agent_usage`, `compute`, `director_time`, `external`. |
| `quantity` | The raw measured quantity for the category (see 9.1). For `compute`: `{"resource": "...", "hours": ...}`. For `director_time`: `{"hours": ..., "start": ..., "end": ...}`. For `external`: `{"amount": ..., "currency": ..., "vendor": ..., "invoice_ref": ...}`. |
| `rates_version` | The version of `rates.json` used to compute `amount`. `null` when no rate exists (see below). |
| `amount`, `currency` | Money in the project currency. `null` when no rate exists. |
| `measured` | `true` only when the quantity came from the measurement source in 9.1. |
| `source` | `runtime-usage`, `job-log`, `review-session`, `invoice`, or `estimate`. |
| `rework`, `rework_reason` | `true` when the work redoes something already submitted. Reason is `director-change` (an approved decision changed), `review-notes` (normal iteration on notes), or `defect` (the work was wrong). |
| `corrects` | ID of the record this one corrects, otherwise `null`. |
| `recorded_by` | The role that wrote the record. |

### Rates

`rates.json` holds the project currency and every rate used to price quantities:

```json
{
  "version": 3,
  "effective_from": "2026-09-01T00:00:00Z",
  "currency": "USD",
  "models": {
    "<model id>": {
      "input_per_mtok": 0.0,
      "output_per_mtok": 0.0,
      "cache_write_per_mtok": 0.0,
      "cache_read_per_mtok": 0.0,
      "source": "<provider pricing page and date checked>"
    }
  },
  "compute": { "<resource>": { "per_hour": 0.0, "source": "..." } },
  "director_per_hour": 0.0
}
```

- The **Director** sets the currency and `director_per_hour`.
- The **Producer** maintains model and compute rates from the provider's published pricing or the actual
  contract, and records the source and date checked. Rates are never guessed.
- Any rate change creates a new version. Earlier versions are kept, so older records stay priced at the rate
  that applied when they were incurred.
- If no rate exists for a quantity, the record is written with the raw quantity, `amount: null`, and
  `rates_version: null`. The Producer reports it as **unpriced** and asks the Director for the rate. It is
  never silently left out.
- External spend in a foreign currency records the original amount and currency in `quantity`, and the converted
  `amount` uses the exchange rate on the invoice date, noted in `note`.

---

## 9.4 Corrections

To fix a wrong record, append a new record with `corrects` set to the wrong record's `id` and quantities and
amount that **reverse** it (negative values), then append a new correct record if needed. Reports net them out;
the history stays intact.

---

## 9.5 Who records what, and when

| Who | Records | When |
|-----|---------|------|
| Every role agent (including the Producer for its own asset-specific work) | `agent_usage` for its task, from the runtime's reported usage | At the end of every work session and at every submission for review |
| The role agent that ran the job | `compute` from the job log | When each job finishes (or fails; failed jobs still cost) |
| Producer | `director_time` from review session timestamps; the Director confirms the hours in the review summary | After each review session, split across the assets reviewed by the time spent on each |
| Producer | `external` from the invoice, with `invoice_ref` | When the invoice is received; the Director confirms it |

Rules:

- **No task, no work.** An agent does not start work without a task ID, so every cost has an owner.
- **If the runtime does not report usage**, the agent records its best available estimate with `measured: false`
  and `source: "estimate"`, states the method in `note`, and tells the Producer. The Producer reports estimates
  separately from measured costs and treats the gap as a problem to fix.
- **Orchestration overhead** that serves many assets (planning, status reports) is recorded against the project
  collection with element `production`, not spread across assets.
- **Shared work** (Visual Bible, material library, effects library, sequence lighting setups) is recorded against
  its own collection. It is reported separately as shared cost and is only allocated to individual assets when the
  Director asks for it, using a stated allocation method.

---

## 9.6 Mirroring to Jira

When the Jira plugin is configured, the Producer mirrors ledger records to the task in Jira:

- `director_time` and `compute` hours as worklogs on the task.
- Money totals (by category) in the task's cost fields or, if the project has none, a cost summary comment
  updated at each submission.
- Each mirrored item references the ledger record IDs.

The ledger remains the source of truth. At each status report the Producer compares Jira totals to the ledger and
reports any difference instead of choosing one.

---

## 9.7 Answering the Director's cost question

When the Director asks what an asset (or shot, element, role, or sequence) has cost, the Producer:

1. Resolves the asset ID and gathers every record for it (and, if asked, its child entities).
2. Nets out corrections.
3. Sums by category, element, and role; separates measured, estimated, and unpriced amounts; and separates rework.
4. Checks completeness: lists tasks for the asset that are in progress with no records since their last session,
   and asks those agents to record their usage before answering, when possible.
5. Replies with the report below. Every figure must be reproducible from the ledger records.

```
Cost report — <asset name> (<asset_id>)
As of: <UTC timestamp> · Currency: <currency> · Rates: v<n> (and earlier where applicable)

Total: <amount>   (measured <amount> · estimated <amount> · unpriced items: <n>)

By category
  Agent usage     <amount>   <input/output/cache tokens by model>
  Compute         <amount>   <hours by resource>
  Director time   <amount>   <hours>
  External        <amount>   <invoices: vendor — ref — amount>

By element                       By role
  concept   <amount>               concept-artist   <amount>
  model     <amount>               modeller         <amount>
  ...                              ...

Rework: <amount> (<share>%) — director-change <amount> · review-notes <amount> · defect <amount>

Not included / caveats
  - Shared costs (not allocated): <collections and amounts, if relevant>
  - Unpriced: <quantities awaiting a rate>
  - Estimates: <records and method>
  - In-progress tasks with unrecorded work: <task IDs>
  - Jira differences: <if any>
```

If the Director asks for a quick answer, the Producer gives the total with the measured/estimated split and the
caveats line, and offers the full breakdown.
