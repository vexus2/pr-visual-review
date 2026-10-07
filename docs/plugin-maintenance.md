# Plugin packaging and releases

PR Visual Review is distributed as a plugin containing one skill. The review code and workflow remain in `pr-visual-review/`, so existing development links continue to work. `skills/pr-visual-review` is an internal relative symlink to that directory; there is no second copy to maintain.

## Package files

| File | Purpose |
| --- | --- |
| `plugin.json` | Portable Agent Plugins manifest |
| `.codex-plugin/plugin.json` | Codex compatibility manifest and presentation metadata |
| `.agents/plugins/marketplace.json` | Codex repository marketplace |
| `.claude-plugin/plugin.json` | Claude Code manifest |
| `.claude-plugin/marketplace.json` | Claude Code repository marketplace |
| `skills/pr-visual-review/` | Bundled skill, helpers, assets, templates, and references |

Both catalogs use the marketplace name `pr-visual-review-marketplace`. The plugin name is `pr-visual-review`. Paths are relative to the repository root. No lifecycle hooks, MCP servers, accounts, or automatic dependency installers are bundled.

The root portable manifest and both compatibility manifests must have the same name and version. The Claude marketplace entry deliberately does not repeat the plugin version; the plugin manifest is authoritative.

## Releasing an update

1. Change the skill or helpers and update the relevant documentation.
2. Bump `version` in `plugin.json`, `.codex-plugin/plugin.json`, and `.claude-plugin/plugin.json` together. A code-only push with the same version is not a reliable update for cached installations.
3. Run `python3 -m unittest discover -s tests -v` and the native checks below. Keep original and annotated image assets public-demo-only.
4. Update CHANGELOG.md and push the release commit to main. Users following this catalog receive the advertised version through their host's update mechanism.

```bash
claude plugin validate .claude-plugin/marketplace.json --strict --json
claude plugin validate .claude-plugin/plugin.json --json
claude --plugin-dir . plugin details pr-visual-review
```

The Claude validator warns that it does not follow the internal skill symlink. Its runtime does follow it. To run a strict validation without that scanner limitation, validate a temporary package copy with internal symlinks materialized. Also inspect the runtime inventory: it must list exactly one `pr-visual-review` skill and zero hooks/MCP servers. The automated package tests verify that a copied package resolves its helpers and assets internally.

## Updates are host-managed

Claude Code users can enable auto-update for this marketplace in `/plugin` → Marketplaces. Third-party marketplaces start with auto-update off; the manifest cannot enable it for users. The current session keeps the loaded version until `/reload-plugins`, while a new session loads the updated version.

For Codex, use the documented marketplace refresh and the installed CLI's plugin installation command. Do not promise a background auto-update schedule that has not been verified for the user's client:

```bash
codex plugin marketplace upgrade pr-visual-review-marketplace
codex plugin add pr-visual-review@pr-visual-review-marketplace
```

This repository is a distribution catalog. Publishing it on GitHub does not imply acceptance into OpenAI's public plugin directory or Anthropic's official marketplace.

Sources checked on 2026-10-07:

- [OpenAI: Package your plugin](https://developers.openai.com/plugins/build/plugins)
- [Claude Code: Plugin manifest reference](https://code.claude.com/docs/en/plugins/manifest-reference)
- [Claude Code: Host and maintain a marketplace](https://code.claude.com/docs/en/plugins/host-marketplace)
- [Claude Code: Install and manage plugins](https://code.claude.com/docs/en/discover-plugins)
