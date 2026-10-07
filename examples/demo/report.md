<!-- pr-visual-review:v1 repo=example/notification-demo pr=123 -->
## PR Visual Review

**Action required 1 · Needs review 1 · Changed 1 · Not verified 1**

Desktop 1280×760 · Mobile 375×844 · Google Chrome via Codex browser connection; running version not recorded

### Mobile: Save moves off-screen — Needs review

![Before / After](<annotated/sp-settings-composite-688551ed30accd22.png>)

original: [Before](<images/sp-before.jpg>) · [After](<images/sp-after.jpg>)

The new form extends past the 375px viewport. Save changes is no longer visible without horizontal scrolling.

- **Action required** · Introduced: Save changes is outside the mobile viewport.

### Desktop: notification controls added — Changed

![Before / After](<annotated/pc-settings-composite-f371e9aacad442d7.png>)

original: [Before](<images/pc-before.jpg>) · [After](<images/pc-after.jpg>)

Email notification controls are present. The existing fields and Save changes button remain visible.

<details>
<summary>Not verified 1</summary>

#### Post-save success state: not verified — Not verified

| Before | After |
| --- | --- |
| Not verified | Not verified |

The demo does not persist settings. A visible Save button is not evidence that saving works.

</details>

<details>
<summary>Conditions and unverified scope</summary>

**Annotations** — Gray = Before reference, blue = change, red = issue. Numbers match the notes.

- Desktop: notification controls added: 1 · Change: Email notification controls were added here.
- Mobile: Save moves off-screen: 1 · Issue: Before: Save is visible. After: the marked right edge clips the form; Save is off-screen to the right \(not drawn into the image\).

- Commits: Before `5849a73be8d4b821e4ba63aa29919b793d3a3c0d` → After `9eb6c95a2b2e7e1ac6480fadbc8a120f0867bb46` / merge-base
- Captured: 2026-10-07T08:18+09:00
- Login: No login
- Conditions: macOS; measured DPR 1.100000023841858; fixed demo data; English page content; browser locale ja; Asia/Tokyo; scroll \(0,0\). Matching CSS viewports on both revisions. Screenshots are unedited browser exports; scrollbar handling can change export dimensions.
- Scope: Desktop + mobile / requested — Local demo · desktop 1280x760 / mobile 375x844 · no live GitHub PR

**Steps per case**

- **Desktop: notification controls added** — /
  - Steps: Open the matching local revision. → Set the measured CSS viewport to 1280x760. → Keep the fixed Design team data and scroll position \(0, 0\). → Inspect the controls and capture the viewport.
  - Why: The local Git diff adds email notification controls and activates the After layout. See change.patch. This is a demo fixture, not a live GitHub PR.
  - Alignment: Workspace settings heading — Same heading position; horizontal scroll kept at zero.
- **Mobile: Save moves off-screen** — /
  - Steps: Open the matching local revision. → Set the measured CSS viewport to 375x844. → Keep the fixed Design team data and scroll position \(0, 0\). → Inspect the controls and capture the viewport.
  - Why: The local Git diff adds email notification controls and activates the After layout. See change.patch. This is a demo fixture, not a live GitHub PR.
  - Alignment: Workspace settings heading — Same heading position; horizontal scroll kept at zero.
  - Action required · Evidence: Before: document width 375px, button x=37..338. After: document width 616px, button x=405..595. See metrics.json and the captures below. / Impact: A user cannot see or reach Save at the initial horizontal scroll position. No full interaction test was performed.
- **Post-save success state: not verified** — /
  - Steps: Click Save changes on the After desktop page. → Observe that the form remains visible without a success message. → Inspect the fixture: submit is prevented and there is no backend request.
  - Why: The requested save-state check needs a backend response; the fixture intentionally has no backend.
  - Alignment: Post-save success state — No genuine successful-save state is available to compare.
  - Before: The fixture has no backend or post-save success view.
  - After: Clicking Save produced no success view. The fixture prevents submission.

**Not verified**

- This is a deliberately constructed demo. The mobile regression is intentional. PR \#123 is an illustrative identifier, not an existing GitHub PR.
- The four app screenshots were captured from real Chrome and inspected. The HTML and Markdown use the standard bundled renderer.
- Saving, email delivery, authentication, touch devices, Safari, and PR image publication were not verified.

Only these screens and states were checked. Zero findings do not establish safety or approval to merge.

</details>
