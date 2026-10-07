# Contributing

不具合報告、ドキュメント改善、再現可能な検証ケースを歓迎します。大きな仕様変更は、実装前にIssueで目的と利用例を共有してください。

## 不具合を報告する

[Issues](https://github.com/vexus2/pr-visual-review/issues) に以下を記載してください。

- Skillのcommit、AIホストとブラウザ、OS、Pythonのバージョン
- 依頼文とPC/SP・ログイン方式の指定
- 期待した結果、実際の結果、再現手順
- 秘密情報を取り除いた最小の設定・ログ・画像

APIキー、Cookie、パスワード、顧客情報、非公開PRのソースや画像を公開Issueへ貼らないでください。可能なら同梱fixtureまたは自作の最小アプリで再現してください。実行環境による未対応と、Skillやスクリプトの不具合を区別できる情報があると調査しやすくなります。

## 変更を提案する

1. Forkして作業ブランチを作ります。
2. 意図した挙動と再現条件を小さく定め、必要なテストを追加します。
3. 以下を実行します。

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q pr-visual-review/scripts
python3 pr-visual-review/scripts/auth_config.py pr-visual-review/templates/auth.example.json
```

4. プラグインをリリースする場合は [plugin-maintenance.md](docs/plugin-maintenance.md) に従い、3つのmanifestのversionをそろえて更新します。
5. Skillの手順を変えた場合は、具体的な利用シナリオで選択が変わることを確認します。実操作・シミュレーション・未検証を分けてPRへ記載してください。
6. READMEと参照文書を更新し、変更内容と検証結果を添えてPRを作成します。

基本のテストはPython標準ライブラリだけで動き、実GitHubへの書き込みやブラウザ接続を必要としません。注釈PNGのテストはrequirements-annotations.txtのPillowが必要で、未導入時はスキップされます。`tests/smoke_server.py` は別途起動する手動ブラウザ検証用fixtureです。実PRへの投稿や画像アップロードを自動テストに無断で追加しないでください。

## 維持したい性質

- ユーザーが指定した確認範囲・投稿範囲を守る
- Before/Afterのコミット・状態・権限・データを照合する
- 不存在、未確認、既存問題、新しい問題を区別する
- 別アカウントのコメントやユーザーの作業ツリーを変更しない
- 秘密値を出力せず、環境依存の未確認事項を成功扱いしない
