# Branching Strategy

This document describes the recommended git branching strategy for features and bugfixes that merge into a dev or staging branch before reaching main.

## Branch Structure

```
main (production-ready)
  ↑
dev (or staging)
  ↑
feature/*  and  bugfix/*
```

## Branch Naming Conventions

| Branch Type | Naming Pattern | Purpose |
|-------------|----------------|---------|
| Features | `feature/<name>` | New functionality (e.g. `feature/asset-system-api`, `feature/app-cli`) |
| Bugfixes | `bugfix/<name>` | Bug fixes (e.g. `bugfix/assetid-validation`, `bugfix/panel-close-icon`) |
| Integration | `dev` or `staging` | Collects all changes before main |
| Production | `main` | Production-ready code only |

## Workflow

### 1. Branch from `dev` for new work

Always branch from `dev` when starting features or bugfixes:

```bash
git checkout dev
git pull origin dev
git checkout -b feature/xyz
# or
git checkout -b bugfix/abc
```

### 2. Merge features and bugfixes into `dev`

Create pull requests to merge completed work into `dev`:

```
feature/xyz → dev (PR)
bugfix/abc  → dev (PR)
```

### 3. Merge `dev` into `main` for releases

When ready to release, merge `dev` into `main` via PR:

```
dev → main (PR)
```

### 4. Keep `dev` in sync after releases

After releasing, ensure `dev` includes the latest from `main`:

```bash
git checkout dev
git merge main
git push origin dev
```

## Best Practices

- **Always branch off `dev`** – Avoid branching directly from `main` unless doing a hotfix.
- **Short-lived branches** – Merge back to `dev` frequently to avoid long-lived branches and painful merges.
- **PRs for everything** – Even for solo work, PRs provide a record and enable review.
- **Linear history** – Consider squash merges or rebasing for cleaner history when merging into `dev`.

## Hotfixes (Optional)

For critical production fixes that cannot wait for the next dev→main cycle:

```bash
git checkout main
git pull origin main
git checkout -b hotfix/critical-fix
# make fix, commit, then:
# hotfix/critical-fix → main (merge)
# hotfix/critical-fix → dev (merge back to avoid regression)
```

## Simplified Alternative

If you don't need a separate staging environment or formal release cadence:

- **`main`** – Always deployable
- **`dev`** – Integration branch
- **`feature/*` / `bugfix/*`** → **`dev`** → **`main`**
