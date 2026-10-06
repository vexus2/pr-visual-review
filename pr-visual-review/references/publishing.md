# 画像掲載とコメント更新

「確認して」だけならローカル結果で終了します。「PRに貼って」等の依頼がある場合は、そのPRへの画像添付とコメント投稿まで実行します。既にある許可を再確認する必要はありません。

## 1. 画像を利用可能な経路でアップロード

推奨順:

1. GitHubの対象PRコメント編集画面の添付UI。ブラウザツールにローカルファイルをuploadする機能がある場合に利用します。GitHub側で生成された画像Markdown/URLを読み取ります。必要に応じてプレビューを開きます。CLIで投稿するなら、UI側ではコメントをsubmitせず、添付URLだけを取得して二重投稿を防ぎます。
2. ユーザーが当該用途に指定した既存画像ストレージ/アップロード手段。利用可能なツールの文書化された操作だけを使います。PRの閲覧者がアクセスでき、保存期間がレビュー期間に足りることを確認します。

GitHubのissue comment REST APIと `gh pr comment` は画像バイナリのアップローダーではありません。ローカルパス、file URL、base64 data URL、ローカルHTTP、認証必須のartifactダウンロードURLを、GitHubで表示可能な画像と扱いません。未公開のGitHub画像upload endpointを推測しません。

画像ホストがなければ、ローカル画像とreport.mdは完成させます。その後、画像の手動添付または利用する保存先の情報だけを求め、「PR掲載だけ未完了」と伝えます。外部サービス新規契約、公開bucket作成、秘密/画像のリポジトリcommit、branch pushで代替しません。

全画像を開いて個人情報・秘密・比較範囲を確認し、アップロード後に対応する画像をブラウザで表示してください。アクセスできる範囲と保持条件を記録します。URL文字列の検証だけでは読者への表示を証明できません。`--images-reviewed` はこの目視とアクセス確認を済ませた実行AIの申告であり、自動検証フラグではありません。

## 2. 本文の生成と投稿

report.json のcaptured画像へ `url` / `detail_url` を設定します。

```bash
# Markdownだけを確認する。ネットワークアクセスなし。
python3 /ABS/SKILL/scripts/review.py render /ABS/RUN/report.json --remote > /ABS/RUN/comment.md

# GitHub上のhead/投稿者/既存コメントを読み、作成か更新かを表示する。書き込みなし。
python3 /ABS/SKILL/scripts/review.py publish /ABS/RUN/report.json > /ABS/RUN/publish-preview.json

# ユーザーが当該PRへの掲載を依頼済みで、画像を確認済みの場合だけ実行する。
python3 /ABS/SKILL/scripts/review.py publish /ABS/RUN/report.json --execute --images-reviewed > /ABS/RUN/publish-result.json
```

ヘルパーは github.com と `gh` を使用します。GitHub Enterpriseには未対応です。Pythonは標準ライブラリのみ、`gh`には対象PRを読む権限とコメント作成/編集権限が必要です。トークン値を引数へ渡しません。

同じPRへの再実行では、コメントの先頭行が次のmarkerと完全一致し、投稿者の数値IDも `gh api user` と一致するものだけを更新します。

本文は今回の依頼範囲全体に置き換わります。「PCのみ」に変更したなら旧SPを混ぜず、今回も対象だが実行できないケースだけを未確認として残します。「SPも追加」なら同じ比較SHAのPC結果を維持して集約します。既存のローカル成果物は残してください。

```text
<!-- pr-visual-review:v1 repo=OWNER/REPO pr=NUMBER -->
```

コメントの全ページを調べます。自分の該当コメントが複数なら勝手に選ばず、ローカル結果を残して対象の指定を求めます。他人のmarker付きコメント、markerのない自分のコメントは編集しません。アカウントを変更した場合、前のアカウントのコメントは更新しません。

撮影SHAとPRの現在headを投稿直前に比較し、変わっていれば再取得・再撮影します。投稿後もheadを再読し、`head_still_current=false` なら投稿自体は完了したが既に旧headの記録であると伝えます。`null` は投稿後の再確認失敗です。GitHub APIにheadとcommentの原子的な更新機能はなく、完全なrace防止は保証できません。同じPRへの実行を並行させず、投稿の不明なtimeout時はコメント一覧を再取得してから再試行します。作成の盲目的リトライは禁止です。

## 3. 投稿後の検証

返されたcomment URLをGitHubで開き、正しいPR・前後SHA・画像・本文が表示されることを確認します。CLI成功だけでは画像掲載成功としません。既存コメント更新では本文だけでなく画像も今回のものか確認します。画像が表示されなければその事実とcomment URL、ローカル画像を提示し、成功扱いにしません。

`gh`を使えない場合は、同じhead・marker・投稿者の条件をブラウザ上で照合して投稿できます。ページングを含む照合ができない場合、他人のコメントを推測で編集しません。UI/APIの書き込みが自動承認審査で拒否されたら、その理由を伝え、別経路で拒否を迂回しません。
