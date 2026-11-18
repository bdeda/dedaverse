# Branching Strategy

Dedaverse uses a single long-lived branch, **`main`**. There is no `dev` or `staging` branch: all work happens on short-lived branches that are cut from `main` and merged back into `main` through a pull request.

## Branch Structure

```
main (always green, always releasable)
  ↑
feature/*  bugfix/*  improvements/*
```

## Branch Naming Conventions

| Branch Type | Naming Pattern | Purpose |
|-------------|----------------|---------|
| Features | `feature/<name>` | New functionality (e.g. `feature/asset-system-api`, `feature/app-cli`) |
| Bugfixes | `bugfix/<name>` | Bug fixes, including urgent production fixes (e.g. `bugfix/assetid-validation`, `bugfix/panel-close-icon`). `bug/<name>` and `fix/<name>` are equivalent |
| Improvements | `improvements/<name>` | Refactors, cleanups, docs and tooling (e.g. `improvements/type-hints`, `improvements/code-cleanup`) |
| Production | `main` | The only permanent branch; production-ready code only |

Use lowercase words separated by hyphens.

## Workflow

### 1. Branch from `main` for new work

Always start from an up-to-date `main`:

```bash
git checkout main
git pull origin main
git checkout -b feature/xyz
# or
git checkout -b bugfix/abc
```

### 2. Commit, push, and get CI green

Push the branch early and often. The CI workflow runs on every push and must be green before the branch is merged (see "Pushing, CI, and PRs" in [AGENTS.md](AGENTS.md)). Fix failures on the branch; never bypass or weaken a check to get a merge through.

### 3. Open a pull request into `main`

```
feature/xyz → main (PR)
bugfix/abc  → main (PR)
```

Even for solo work, a PR records what changed and why, and gives CI and any reviewer a single place to look. Merge only when CI is green. Either a merge commit or a squash merge is fine; use one consistently for a given PR.

### 4. Delete the branch after merging

Once merged, delete the remote and local branch. Start the next piece of work from a fresh `main`.

## Keeping a Branch Up to Date

If `main` has moved while your branch is open, bring the changes in so you are testing against what will actually ship:

```bash
git fetch origin
git rebase origin/main        # or: git merge origin/main
```

Rebase only branches that nobody else is working on; if in doubt, merge `main` into the branch instead. After a rebase, push with `git push --force-with-lease`.

## Best Practices

- **`main` is always releasable** – Never merge work that breaks the build, the tests, or the CI gates.
- **Short-lived branches** – Merge back to `main` frequently. A branch that lives for weeks collects conflicts; split large work into pieces that can each land on their own.
- **Keep unfinished work out of the way** – If a feature cannot land in one piece, merge it in steps that leave existing behaviour unchanged (for example new modules that nothing imports yet, or code behind an off-by-default option).
- **One purpose per branch** – Keep unrelated changes (a docs fix, a refactor, a new feature) on separate branches so each PR is easy to review and revert.
- **PRs for everything** – Do not commit directly to `main`.

## Hotfixes

A critical production fix follows the same path as any other change, just faster: branch from `main` as `bugfix/<name>`, open a PR into `main`, and merge as soon as CI is green. There is no second branch to merge it back into.

## Releases

`main` is what ships. If you need to mark a release, tag the commit on `main` (for example `git tag v1.2.0 && git push origin v1.2.0`) rather than creating a release branch.
