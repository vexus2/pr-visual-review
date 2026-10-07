# Changelog

## 0.1.3 — 2026-10-07

- Markdown report and PR comment are rewritten to be skimmed. The body contains only changed and needs-review cases (action-required first) with images and a short finding. Unchanged, new/removed, and unverified cases, replay steps, run conditions, commits, and limitations are collapsed at the end. Shared browser/conditions are stated once; per-case values appear only when they differ. The first live run produced a 9,800-character comment that reviewers did not read.
- The summary line now counts changed / no-change / new-or-removed / unverified cases separately, so "0 unverified" no longer hides cases that had no Before.
- Plainer labels in both languages, for example "変更あり" instead of "意図した変更を確認"; timestamps are shown to the minute.
- SKILL.md limits the default plan to the screens the diff changes (at most four cases unless asked), keeps findings to two sentences, and forbids mentioning other skills or tools in the report.
- Validation notes record the first live PR posting (private repository, 13 images) and why the format changed. README demo screenshot regenerated from the current renderer.
- Report schema is unchanged; existing report.json files render in the new layout.

## 0.1.2 — 2026-10-07

- Fix: `publish` no longer crashes on a PR comment whose author account was deleted (`user: null`).
- Fix: paginated comment lookup joins `gh api --paginate` pages locally instead of requiring the newer `--slurp` flag.
- Fix: `review.py --help` and report validation no longer fail when the English label asset is missing; it is loaded on first use.
- Add GitHub Actions tests (Python 3.10 / 3.12, with and without Pillow), SECURITY.md, and issue templates.
- Move packaging and release steps into CONTRIBUTING.md; `docs/` is now untracked working notes.
- Update the Codex and Claude Code adapter notes to the plugin installation path and remove the standalone-skill instructions.
- Remove the root-level `pr-visual-review` compatibility symlink; the skill lives only under `skills/pr-visual-review/`.

## 0.1.1 — 2026-10-07

- Store the bundled skill as real files under `skills/pr-visual-review/`. Codex cache copying skips symlinks, which left the skill missing in the initial 0.1.0 package.
- Keep the former root-level skill path as a compatibility link for local development.
- Add a cache-copy regression test and recheck native package loading.

## 0.1.0 — 2026-10-07

- Package PR Visual Review for Codex and Claude Code, with repository marketplaces for both hosts.
- Bundle the existing review skill, screenshot annotation helpers, report generation, and login configuration validation.
- Preserve the standalone skill path for existing installations.
- Document native installation, updates, optional Claude Code auto-updates, and versioning requirements.
- Checked against Codex CLI 0.158.0 and Claude Code 2.1.284.
