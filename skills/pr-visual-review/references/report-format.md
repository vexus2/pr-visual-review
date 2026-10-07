# report.json v2（v1読み取り互換）

`templates/report.json` を run ディレクトリにコピーして記録します。画像の基準パスは report.json の親ディレクトリです。ローカル report.md も同じ場所へ保存してください。Python 3.10以上、基本処理は標準ライブラリだけを使用します。注釈付きPNGの書出しのみPillowが必要です。

| フィールド | 内容 |
| --- | --- |
| schema_version | 新しい実行は `2`。保存済みの `1` も読み取り可能 |
| language | `en` または `ja`。省略時は旧形式と同じ日本語。見出し・状態ラベルだけを切り替え、所見や操作等の本文は書き換えない |
| scope | `devices: ["pc"]` / `["sp"]` / `["pc","sp"]`、`basis: explicit`または`default`、`note: 選定理由と範囲` |
| repository / pr | github.com の `owner/repo` と正整数 |
| before_sha / head_sha | 実際に起動・撮影した完全な40桁SHA |
| comparison | `merge-base` または `explicit-base` |
| captured_at | timezone付きISO日時 |
| browser | 実ブラウザ製品/version。未起動ならその旨を明示 |
| authentication | 任意。modeとbefore/after/equivalenceの確認状態だけ。詳細は [authentication.md](authentication.md) |
| conditions | viewport、DPR、locale、timezone、fixture、scroll、OS、zoom等の共通条件 |
| cases | 画面状態のリスト。1 case内のBefore/Afterは同じ条件にそろえる |
| limitations | 未確認browser、認証不可、除外範囲、条件相違等。ケースなしの場合は選定しなかった根拠を必ず入れる |

case は `id`（一意の小文字slug）、`title`、`route`、`reason`（コード/参照関係による選定根拠）、`steps`（同じ状態に到達する操作の配列）、`result`、`finding`、`before`、`after` を持ちます。v2では以下も必須です。

画像内の位置を示す場合はcaseへ `annotations` を追加します。[注釈の仕様と書出し手順](annotations.md)を参照してください。原画像のx/y/width/heightを0〜1に正規化し、枠・番号・説明を対応させます。旧レポートの注釈なし表示も引き続き使えます。`annotate` が書き出す派生JSONには、前後とも撮影したcaseに `composite_image` / `composite_sha256` / `composite_fingerprint`（投稿時は `composite_url`）が、片側だけのcaseの枠付きsideに `annotated_image` 等が入ります。

```json
{
  "device": "sp",
  "viewport": {"width": 375, "height": 844},
  "alignment": {
    "method": "element",
    "anchor": "通知設定の見出し",
    "note": "前後とも見出しをviewportの上端から24pxへ配置"
  },
  "issues": []
}
```

viewportはCSS pxの正整数です。未撮影caseでは予定値とその旨を条件に記録します。scope外のdeviceのcaseは拒否します。対象に含めた各deviceはcaseを作り、実行できなければunverifiedにします。ケースなしなら画面影響なし等の理由をlimitationsへ入れます。URLの前後のhost/portと実行記録へのパスは `reason` や `steps` に記録できます。秘密のquery値を入れません。

依頼されたdesktop/mobileやbrowserを追加するときは、同じreportの別caseに追加します。caseの `browser` / `conditions` は個別条件です。1回のPR投稿はreport全体を置換するので、今回対象の全caseを集約してから投稿してください。古いheadのcaseを新しいheadのreportに混ぜません。今回も対象に含めるが確認できないcaseだけを未確認とし、「PCのみ」で対象外になったSP等は持ち越しません。詳しくは [capture-plan.md](capture-plan.md) を参照してください。

`result`:

- `intended`: PRの意図に沿う変化を画像で確認しました。
- `needs-review`: 意図しない可能性がある重なり/欠け等を観測しました。断定と推測を分けます。
- `unchanged`: 同じ状態の前後画像で見た目の変化を確認できませんでした。
- `unverified`: 起動・認証・条件不一致等で比較を完了できませんでした。

## 個別の問題

`issues` は問題がなければ空配列です。v2のneeds-reviewでは1件以上必要です。例:

```json
{
  "origin": "pre-existing",
  "priority": "optional",
  "summary": "ページ全体の横スクロール",
  "evidence": "Before/Afterともdocument幅916px。画像でも既存の横スクロールを確認",
  "impact": "今回悪化した証拠はありません。既存レイアウトの改善対象です"
}
```

分類と撮影基準は [capture-plan.md](capture-plan.md) に従います。既存/悪化の断定にはBefore画像、問題の記録にはAfter画像が必要です。requiredはintroduced/worsenedかつcase結果needs-reviewに限ります。unknownはinvestigateだけです。横スクロールや折り返しだけを必須修正と判定しません。summaryの件数は指摘数でありcase数とは異なります。

v1にはscope/alignment/issuesを追加せず、そのまま読めます。旧形式は「対象端末の記録なし」として表示し、本文から由来・必須修正の件数を推測しません。v2への変更は、人が根拠を確認して必要な項目を記入するときだけ行います。コメントmarkerのv1はコメント識別用の固定値であり、reportのschema_versionとは別です。

before / after:

```json
{"state": "captured", "image": "images/settings-before.png"}
```

captured は文脈が分かる画面画像が必須です。`detail_image` に変更箇所の拡大画像を任意で追加できます。画像はPNG/JPEG/WebP、reportディレクトリ内の相対パスです。撮影時のviewportが文脈を満たせば全ページスクロール画像は必須ではありません。画像を保存して開き、真のブラウザ証拠であることを確認するのは実行AIの責任です。ヘルパーは画像形式の先頭識別子のみを検証し、画面内容の正しさや完全なデコードを保証しません。

投稿用にアップロードが完了したら、同じオブジェクトに `url`、拡大画像があれば `detail_url` を設定します。元のローカル画像も残します。

```json
{"state": "absent", "note": "新規routeです。Beforeのルート定義に存在しないことを確認しました。"}
```

```json
{"state": "unverified", "note": "Beforeは依存導入に失敗し、起動できませんでした。"}
```

absent/unverified には比較画像を入れません。404などを調査で保存した場合は別の診断資料として扱います。一方が未確認ならcase全体のresultも未確認です。両方capturedでない状態のunchangedは拒否します。

## 実行

```bash
python3 /ABS/SKILL/scripts/review.py render /ABS/RUN/report.json > /ABS/RUN/report.md
python3 /ABS/SKILL/scripts/review.py render /ABS/RUN/report.json --format html > /ABS/RUN/report.html
python3 /ABS/SKILL/scripts/review.py render /ABS/RUN/report.json --remote > /ABS/RUN/comment.md
```

Markdown（report.mdとPRコメント）の構成は固定です。冒頭に「要対応 / 要確認 / 変更あり / 変化なし / 新規・削除画面 / 未確認」の件数（0件は要対応以外省略）と端末・ブラウザを1行。本文には `needs-review` と、前後ともcapturedの `intended` だけを「見出し・Before/After画像・所見・指摘の一行」で並べ、要対応のあるケースを先頭にします。`unchanged`、片側absentの新規・削除画面、`unverified` はそれぞれ折りたたみにまとめます。コミット、撮影日時、認証、条件、各ケースの操作手順・理由・撮影基準・absent/unverifiedの理由、指摘の根拠と影響、未確認事項は末尾の折りたたみに一度だけ出します。caseの `browser` / `conditions` は report全体と異なるときだけ表示します。読む側が短時間で差分を把握できるよう、`finding` は2文以内に収めてください。

HTMLはJavaScript・外部フォント不要で、CSSを埋め込んだオフライン表示です。画像はreport.jsonと同じディレクトリ基準の相対パスなので、HTMLも同じ場所に保存します。移動するときはimagesを含むrun全体を移します。画像は原寸を超えて拡大せず、クリックで元画像を表示します。既存成果物を再表示する場合は別名へ保存し、撮影日時/SHAを書き換えません。

両方の出力を目視し、前後画像・所見・対象範囲が対応することを確認します。生成された文字列はエスケープされます。HTML追加は撮影範囲を増やす指示ではありません。
