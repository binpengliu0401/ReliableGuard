# Pre-Push Documentation Checklist

A push is treated as a project **node**: reaching it means every record file — both the
GitHub-tracked ones and the gitignored local ones — must be current. This is enforced by
`hooks/pre-push` (install once after cloning: `bash scripts/install-hooks.sh`).
Emergency bypass (avoid): `git push --no-verify`.

Before every push, the hook checks:

1. **CHANGELOG.md** — an entry was added under `[Unreleased]`.
   *Hard gate: the push is rejected if `CHANGELOG.md` is not among the commits being pushed.*
2. **README.md** — updated if the change adds, moves, or removes a tracked file, directory,
   command, or workflow that the project-structure / usage sections describe.
   *Soft warning: the hook warns if tracked code changed but `README.md` did not.*
3. **CLAUDE.md** — the "Code Task Checklist" / Status / decisions reflect this node.
   *Hard gate (see below).*
4. **memory/** — the roadmap memory mirrors this node's durable decisions/facts.
   *Soft warning: the hook warns if no `memory/*.md` changed since the last push, but does not
   block (memory hygiene — not every node produces a fact worth recording).*

## How the local-record gate works (items 3–4)

`CLAUDE.md` and `memory/` are gitignored, so they never appear in git history and cannot be
checked from the pushed commits. Instead the hook keeps a content-hash baseline in
`.git/doc_push_state` (local, untracked) recording, at each successful push, the pushed `HEAD`
and the hashes of `CLAUDE.md` and the memory `*.md` files.

On the next push the hook compares:

- **Same `HEAD` as last push** (e.g. retry after a network failure): the gate is skipped.
- **New `HEAD` (a new node)**: if `CLAUDE.md` is byte-for-byte unchanged since the last push,
  or no `memory/*.md` changed, the push is **rejected** — update the records first.
- **First run** (no baseline yet): the baseline is recorded and the gate is not enforced.

Only `CLAUDE.md` is a hard gate. The `memory/` check is a non-blocking warning: if no
`memory/*.md` changed since the last push the hook prints a reminder but still allows the push.

The memory directory defaults to the Claude memory path derived from the repo location and can
be overridden with `RG_MEMORY_DIR`. On a fresh clone / CI where the local files are absent, the
relevant checks are skipped so legitimate pushes are not blocked. `git push --no-verify` bypasses
all checks for one push.
