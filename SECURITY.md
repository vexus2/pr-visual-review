# Security Policy

日本語での報告も受け付けます。

## Supported versions

Only the latest release on `main` receives fixes. The plugin version is recorded in `plugin.json` and [CHANGELOG.md](CHANGELOG.md).

## What this project does and does not do

Knowing the boundaries helps decide whether a finding belongs here.

- The bundled scripts validate `report.json`, render Markdown/HTML, draw annotation frames, and create or update **one comment owned by the current `gh` user** on a github.com pull request. Writes happen only with `--execute`.
- The scripts never start your app, drive a browser, upload images, read credential values, or execute commands from configuration files. Those steps are performed by the AI host under its own permissions.
- Report text is escaped before it reaches Markdown or HTML. Image paths must stay inside the report directory; hosted image URLs must be public HTTPS.
- `auth_config.py` validates a login recipe's shape only. It does not open the referenced environment variables or files.

Behavior of the AI host, the browser integration, GitHub, or your application is outside this project's control. Report those to their vendors.

## Reporting a vulnerability

Please report privately through GitHub's **Report a vulnerability** form on this repository's Security tab. If that form is unavailable, open an issue that only says you have a security report and how to reach you; do not include details in the public issue.

Include the plugin version, the helper command or skill step involved, and a minimal reproduction that contains no real credentials, customer data, or private PR content.

You can expect an acknowledgement within 7 days. Fixes are released as a new plugin version with a CHANGELOG entry; please allow time for that release before public disclosure.

## Out of scope

- Findings that require the user to disable the documented safeguards (for example running `publish --execute` without reviewing images).
- Prompt-injection against the AI host itself. The skill text already instructs the agent to treat repository content as data, but enforcement lives in the host.
- Issues in third-party tools such as `gh`, Pillow, or the browser integration.
