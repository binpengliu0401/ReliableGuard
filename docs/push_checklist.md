# Pre-Push Documentation Checklist

Enforced by `hooks/pre-push` (install once after cloning: `bash scripts/install-hooks.sh`).
Emergency bypass (avoid): `git push --no-verify`.

Before every push, confirm:

1. **CHANGELOG.md** — an entry was added under `[Unreleased]` describing this change.
   *Hard-gated: the push is rejected if `CHANGELOG.md` is not among the commits being pushed.*
2. **README.md** — updated if the change adds, moves, or removes a tracked file, directory,
   command, or workflow that the project-structure / usage sections describe.
   *Soft warning: the hook warns if tracked code changed but `README.md` did not.*
3. **Framework decisions** — any design or scope decision agreed this session is recorded in
   `CLAUDE.md` (Status / roadmap) and in the `memory/` roadmap.
   *Reminder only: these are gitignored, local-only files and cannot be verified from git.*
4. **Task status** — the `CLAUDE.md` "Code Task Checklist" reflects what is done / pending for
   this change (check off completed tasks, note resolved decisions).
   *Reminder only: gitignored, local-only.*

Items 3–4 live in gitignored local files, so they cannot be machine-verified from git history.
When the hook runs interactively (a terminal `git push`), it prints this list and requires an
explicit `y` confirmation. Non-interactive pushes (e.g. the IDE push button, CI) still get the
hard CHANGELOG gate and the README warning, but the items 3–4 confirmation is shown as a
reminder only.
