# Pre-Push Checklist

`hooks/pre-push` enforces one rule (install once after cloning: `bash scripts/install-hooks.sh`;
emergency bypass, avoid: `git push --no-verify`):

- **CHANGELOG.md** must be updated in the commits being pushed.
  *Hard gate: the push is rejected if `CHANGELOG.md` is not among the pushed commits.* Add an entry
  under `## [Unreleased]` describing the change, in the same commit as the change.

That is the only enforced gate. The earlier CLAUDE.md / memory / README content-hash gates were
removed (2026-06-09) when CLAUDE.md became a thin router: the change record lives in CHANGELOG.md,
and CLAUDE.md / `memory/` are updated by judgement when a node changes the overview or produces a
durable fact (not enforced).
