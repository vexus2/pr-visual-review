# 画像上の変更箇所・問題箇所

AIが原画像を確認して選んだ領域に、枠と番号を重ねます。ピクセル差分の自動検出ではありません。UIの崩れを見つけるのも実行AIの役割で、ヘルパーは指定された注釈を検証・描画します。

## 表示の意味

- Beforeの灰色枠: 比較用の参照箇所。Beforeに問題があるという意味ではありません。
- Afterの青色枠: 確認した変更箇所。
- Afterの赤色枠: 指摘に対応する問題箇所。今回発生か既存かはissuesのoriginを読みます。
- 同じ番号: 同じ変更・指摘への参照。番号と説明を併記し、色だけに頼りません。

原画像は上書きしません。HTMLは原画像の上にCSSの枠を重ね、注釈なし表示と原画像リンクも残します。Markdown/GitHubは別に書き出したPNGと原画像リンクを使います。PNGには番号とCHANGE/ISSUE/REFの短いラベル、本文には詳しい説明を載せます。

## 座標の決め方

保存した画像を開き、表示上の幅W・高さHに対して矩形を指定します。`x=左端/W`、`y=上端/H`、`width=領域幅/W`、`height=領域高/H`。値は0〜1です。EXIF回転がある場合は回転後の表示を基準にします。

実viewportとスクリーンショットのピクセル寸法はDPR・zoom・スクロールバー・切り抜きにより異なることがあるため、DOMの座標をそのまま使いません。原画像を縮小表示しても、枠は同じ割合で追従します。

領域は変更や問題が分かる最小限の範囲とし、説明に必要な周辺は元の文脈画像に残します。番号札で重要な文言が隠れないか、生成後に画像を開いて確認します。

画面外にあるものを存在するように描かないでください。保存ボタンが右へはみ出した場合は、BeforeのボタンとAfterの画面右端・切れているフォームを参照し、「ボタンは画面外」と説明します。Beforeに存在しない新規UIならBefore枠を省略できます。比較条件がそろわずunverifiedのcaseには枠を付けません。

## report v2の追加項目

```json
"annotations": [
  {
    "id": 1,
    "kind": "change",
    "label": "Email notification controls were added here.",
    "after": {"x": 0.19, "y": 0.44, "width": 0.62, "height": 0.195}
  },
  {
    "id": 2,
    "kind": "issue",
    "issue_index": 0,
    "label": "Before: Save is visible. After: the right edge clips the form; Save is off-screen.",
    "before": {"x": 0.10, "y": 0.58, "width": 0.80, "height": 0.065},
    "after": {"x": 0.88, "y": 0.21, "width": 0.115, "height": 0.58}
  }
]
```

これは形式の説明用です。実際は該当するcaseにだけ注釈を入れます。

- idはcase内で一意の1〜99、最大20領域。
- kindはchangeまたはissue。issue_indexはcase.issuesの0始まりの番号で、issueの場合だけ必須。
- before/afterは少なくとも一方が必要。対応する側がcapturedであること。
- labelは表示言語に合わせた説明です。記号・HTML等はエスケープされます。
- 範囲外、ゼロ幅、NaN/Infinity、重複番号、未撮影側の枠は拒否します。

## 静的PNGとレポート

HTMLだけなら追加ライブラリは不要です。PNGの書き出しだけPillowを使います。

```bash
python3 -m pip install -r /ABS/SKILL/requirements-annotations.txt
python3 /ABS/SKILL/scripts/review.py annotate /ABS/RUN/report.json --out /ABS/RUN/report.annotated.json
python3 /ABS/SKILL/scripts/review.py render /ABS/RUN/report.annotated.json > /ABS/RUN/report.md
python3 /ABS/SKILL/scripts/review.py render /ABS/RUN/report.annotated.json --format html > /ABS/RUN/report.html
```

環境の依存導入ルールに従ってください。Pillowを導入できない場合も、`render report.json --format html`で注釈を表示できます。PNGがないままMarkdownを「注釈付き」として出力・投稿しません。

`annotate`は原JSONを変更せず、同じディレクトリの別JSONへ保存します。画像は `annotated/` にPNGとして書き出します。元画像や領域が変わると異なるファイル名になります。派生JSONのannotated_image・annotated_sha256・annotation_fingerprintはヘルパーが設定する値なので、手で書き換えません。PNGは透明度を保持し、EXIFの回転に従います。原画像は変更しません。

Markdown/投稿の生成時には、元画像・注釈内容・派生PNGのハッシュを再照合します。変更があれば再exportしてください。HTMLのCSS表示は常に現在の原画像と領域を使います。

PRへ掲載するときは、原画像のurlに加え、枠を付けた各sideの `annotated_url` も設定します。必要なPNG/URLが不足している場合は投稿前に停止します。再exportでは古いannotated_urlを引き継がないため、生成後にアップロード先を設定してください。
