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
python3 -m compileall -q skills/pr-visual-review/scripts
python3 skills/pr-visual-review/scripts/auth_config.py skills/pr-visual-review/templates/auth.example.json
```

4. Skillの手順を変えた場合は、具体的な利用シナリオで選択が変わることを確認します。実操作・シミュレーション・未検証を分けてPRへ記載してください。
5. READMEと参照文書を更新し、変更内容と検証結果を添えてPRを作成します。GitHub Actionsが同じテストをPython 3.10 / 3.12（Pillowあり・なし）で実行します。

基本のテストはPython標準ライブラリだけで動き、実GitHubへの書き込みやブラウザ接続を必要としません。注釈PNGのテストはrequirements-annotations.txtのPillowが必要で、未導入時はスキップされます。`tests/smoke_server.py` は別途起動する手動ブラウザ検証用fixtureです。実PRへの投稿や画像アップロードを自動テストに無断で追加しないでください。

`docs/` はGit管理外の作業メモ置き場です。利用者向けの説明はREADME、Skillの仕様は `skills/pr-visual-review/references/` に書いてください。

## リリース手順

PR Visual Reviewは1つのSkillを含むプラグインとして配布します。実体は `skills/pr-visual-review/` の実ファイルです。Codexのキャッシュコピーはsymlinkを無視するため、このディレクトリをsymlinkに置き換えてはいけません。`tests/test_plugin_package.py` がその状態を再現して検証します。

| ファイル | 役割 |
| --- | --- |
| `plugin.json` | 共通のAgent Plugins manifest（versionの正本） |
| `.codex-plugin/plugin.json` | Codex用manifestと表示メタデータ |
| `.agents/plugins/marketplace.json` | Codex用リポジトリカタログ |
| `.claude-plugin/plugin.json` | Claude Code用manifest |
| `.claude-plugin/marketplace.json` | Claude Code用リポジトリカタログ（versionは書かない） |

カタログ名は両ホストとも `pr-visual-review-marketplace`、プラグイン名は `pr-visual-review` です。Hooks、MCPサーバー、アカウント、依存の自動導入は同梱しません。

1. 変更とドキュメント更新を済ませ、テストが通ることを確認します。
2. `plugin.json`、`.codex-plugin/plugin.json`、`.claude-plugin/plugin.json` の `version` を同じ値へ上げます。コードだけ変えて同じversionでpushしても、キャッシュ済みのインストールには届きません。
3. CHANGELOG.mdに項目を追加し、動作確認したCodex CLI / Claude Codeのバージョンを併記します。
4. Claude Codeの検証コマンドを実行します。

```bash
claude plugin validate .claude-plugin/marketplace.json --strict --json
claude plugin validate .claude-plugin/plugin.json --strict --json
claude --plugin-dir . plugin details pr-visual-review
```

5. mainへcommitし、`vX.Y.Z` のタグを付けてpushします。

```bash
git tag -a v0.1.2 -m "pr-visual-review 0.1.2"
git push origin main --tags
```

更新の配信はホスト任せです。Claude Codeの第三者カタログは自動更新が既定で無効で、配布側からは有効にできません。Codexは `codex plugin marketplace upgrade` と `codex plugin add` で更新します。このリポジトリは配布カタログであり、各社の公式ディレクトリへの掲載を意味しません。

## 維持したい性質

- ユーザーが指定した確認範囲・投稿範囲を守る
- Before/Afterのコミット・状態・権限・データを照合する
- 不存在、未確認、既存問題、新しい問題を区別する
- 別アカウントのコメントやユーザーの作業ツリーを変更しない
- 秘密値を出力せず、環境依存の未確認事項を成功扱いしない
