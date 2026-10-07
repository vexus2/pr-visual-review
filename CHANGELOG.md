# Changelog

## 0.1.1 — 2026-10-07

- Store the bundled skill as real files under `skills/pr-visual-review/`. Codex cache copying skips symlinks, which left the skill missing in the initial 0.1.0 package.
- Keep the former root-level skill path as a compatibility link for local development.
- Add a cache-copy regression test and recheck native package loading.

## 0.1.0 — 2026-10-07

- Package PR Visual Review for Codex and Claude Code, with repository marketplaces for both hosts.
- Bundle the existing review skill, screenshot annotation helpers, report generation, and login configuration validation.
- Preserve the standalone skill path for existing installations.
- Document native installation, updates, optional Claude Code auto-updates, and versioning requirements.
