# Public demo: notifications and a mobile regression

This example demonstrates the output of PR Visual Review with a small, intentionally broken local app. It is not a real GitHub PR. `#123` is an illustrative identifier required by the report format.

## What was actually run

1. `tests/demo_server.py` created two commits in a temporary Git repository and started separate worktrees on loopback HTTP ports.
2. Codex inspected the change and used real Chrome to open both revisions at measured CSS viewports of 1280×760 and 375×844.
3. Four screenshots were exported without editing. The mobile document width and Save button bounds were read from the rendered DOM; see [metrics.json](metrics.json).
4. Save changes was clicked on desktop. The fixture prevents submission and has no backend, so the success state was recorded as **not verified**, not passed.
5. Regions were selected on the saved images: blue around the new desktop controls, gray around the Before Save button, and red at the clipped right edge in After. The off-screen button itself was not drawn into the image.
6. The standard helper exported separate PNGs and [report.annotated.json](report.annotated.json), then rendered [Markdown](report.md) and [HTML](report.html). The README overview image is a Chrome screenshot of that HTML.

The expected desktop addition is the email notification panel. The deliberate mobile defect is a fixed-width form that moves Save changes outside the viewport. The fixture must remain broken to reproduce the finding.

## Reproduce

From the repository root:

```bash
python3 tests/demo_server.py
```

Open the printed Before and After URLs with your agent's browser tool. Match the measured viewport, fixed demo data, and scroll position. Capture both revisions, inspect them, and update the evidence record from your own observations.

The server rewrites `run.json` and `change.patch` with fresh temporary commits and ports. Do not present the existing screenshots as captures of those new commits. Either preserve the current sample or replace **all** corresponding captures, metrics, and report metadata together. Ctrl-C stops the servers and removes their temporary worktrees.

To render the checked-in evidence without recapturing:

```bash
python3 -m pip install -r skills/pr-visual-review/requirements-annotations.txt
python3 skills/pr-visual-review/scripts/review.py annotate examples/demo/report.json --out examples/demo/report.annotated.json
python3 skills/pr-visual-review/scripts/review.py render examples/demo/report.annotated.json > examples/demo/report.md
python3 skills/pr-visual-review/scripts/review.py render examples/demo/report.annotated.json --format html > examples/demo/report.html
python3 -m http.server 8000 --bind 127.0.0.1 --directory examples/demo
```

Open `http://127.0.0.1:8000/report.html`. The screenshot exports may omit scrollbar areas; comparison conditions refer to the measured CSS viewport, not the JPEG dimensions. This is a visual review, not a pixel-diff test.

No login, email delivery, real save, cloud upload, or GitHub comment was performed. The app and its captures contain only public demo data.
