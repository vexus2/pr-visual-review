# PR Visual Review

PRの差分を読んだAIがローカルWebアプリを起動し、実ブラウザで変更前後を撮影して、確認範囲と所見を残すSkillです。Codex / Claude Code向けの初版です。

**Ask your coding agent to inspect a PR and capture before/after visual evidence.**

```text
$pr-visual-review PR #123をPCとSPの両方で確認して。まずはローカル保存だけ。
```

| Before | After |
| --- | --- |
| ![変更前の通知設定モーダル](examples/smoke/images/before-detail.jpg) | ![変更後の通知設定モーダル](examples/smoke/images/after-detail.jpg) |

上の画像は同梱のローカルfixtureを実Chromeで撮影したものです。キャンセルと保存ボタンの間隔を変更しています。[比較レポート例](examples/smoke/report.md)と[検証範囲](examples/validation.md)を確認できます。顧客サイトや実PRの画像は含めていません。

画像比較ライブラリやnpm CLIではありません。画面選定・モーダル等の操作・起動方法の判断はAIが行います。Playwrightテストの事前作成は不要です。スキルを入れるだけでブラウザ接続が追加されるわけではありません。

## 導入

`pr-visual-review/` ディレクトリ全体をインストールします。SKILL.mdだけをコピーしないでください。既存の同名スキルがある場合は、上書きせず内容を比較してください。

macOS / Linuxの例です。Python 3.10以上・Git・ブラウザ連携が必要です。対象アプリ固有のruntimeも用意してください。

```bash
mkdir -p ~/src
git clone https://github.com/vexus2/pr-visual-review.git ~/src/pr-visual-review
cd ~/src/pr-visual-review

# Codex: cloneしたSkillの実体を参照します。既存リンクは上書きしません。
mkdir -p ~/.agents/skills
ln -s "$PWD/pr-visual-review" ~/.agents/skills/pr-visual-review

# Claude Codeで使う場合はこちらも実行
mkdir -p ~/.claude/skills
ln -s "$PWD/pr-visual-review" ~/.claude/skills/pr-visual-review
```

リンクを使わない場合はSkillディレクトリ全体をコピーしても使えます。対象プロジェクトだけで使う場合はそれぞれ `.agents/skills/`、`.claude/skills/` に配置します。新しいセッションで検出を確認してください。コピーの場合の更新は手動です。Windowsでの導入手順は未検証です。

配置仕様: [OpenAI Skills](https://developers.openai.com/codex/skills)、[Claude Code Skills](https://code.claude.com/docs/en/skills)。ブラウザ: [Claude Code Chrome連携](https://code.claude.com/docs/en/chrome)。Codexではそのセッションにあるブラウザツールを使います。

## 使い方

```text
$pr-visual-review PR #123 の画面変更を確認して。
$pr-visual-review PR #123 をSPのみ375px幅で確認して。ローカル保存だけ。
$pr-visual-review PR #123 をPCのみ確認して。
$pr-visual-review PR #123 をPCとSPの両方で確認して。
$pr-visual-review https://github.com/owner/repo/pull/123 の変更前後のスクショをPRに貼って。
```

Claude Codeでは `/pr-visual-review` を使用できます。通常の自然言語依頼でも内容が一致すればスキルの選択対象になります。

「確認して」はローカル保存、「PRに貼って」は画像添付とPRコメントまでが対象です。「PCのみ」「SPのみ」「両方」を指定できます。対象外の端末は撮影せず、未確認件数にも足しません。SPはブラウザのスマホ幅での確認で、実機・タッチ操作の検証とは区別します。

幅を指定すればそれを優先します。指定のないサイズはプロジェクトの既定値、なければPC 1280×1000 / SP 390×844 CSS pxです。端末指定自体がなければPCのみで進め、開始時に範囲を伝えます。「スマホ表示も」は現在の範囲にSPを追加し、「PCのみ」への変更なら以前のSP結果を持ち越しません。「Safariも」は実Safariを操作できる場合だけ実施します。WebKitをSafariと表示しません。

成果物は `report.json`・`report.md`・`report.html` と画像です。同じJSONから標準のHTMLを生成するため、セッションごとに独自のHTML生成コードを書く必要はありません。「今回発生」「今回悪化」「既存」「因果未確定」と「PRで要対応」「任意改善」「要調査」を分けて表示します。既存の横スクロールや通常の折り返しを、そのまま今回のPRの必須修正とは扱いません。

## ログイン方法を指定する

```text
$pr-visual-review を読み直して、PR #123をSPのみ375px幅で確認して。
ログインはプロジェクトの .pr-visual-review.json に従って。ローカル保存だけ。
```

```text
PR #123をPCのみ確認して。/signinを開いたらログインは自分で行います。
ログイン後はサイト管理者として /settings/site を確認してください。
```

「既存セッションを使う」「通常ログイン」「自分でログインする」「開発用fixture」の4方式と、ログイン不要の指定に対応します。設定ファイルは任意です。今回の指示 → 明示した設定ファイル → 対象プロジェクトの `.pr-visual-review.json` → 既存手順の順に優先します。

繰り返し使う場合は [設定テンプレート](pr-visual-review/templates/auth.example.json) を対象プロジェクトへコピーし、URLのパス・必要なrole・操作・成功確認条件を設定してください。テンプレートは環境変数名を参照する例です。別のローカルJSON内のキーを参照することもできます。パスワード等の値は設定ファイルやSkillへ埋め込みません。

```bash
python3 /ABS/SKILL/scripts/auth_config.py /ABS/PROJECT/.pr-visual-review.json
```

検証スクリプトは秘密値の取得やログインを行いません。実際の操作はAIがブラウザ機能で行い、Before/Afterの権限・データを照合します。レポートへは方式と確認状態だけを記録します。設定の全項目と例は [認証設定](pr-visual-review/references/authentication.md) にあります。

## 必要なものと初版の範囲

- Git、対象リポジトリと依存導入/起動に必要なruntime。
- 実Google Chromeを操作し、スクリーンショットをファイルへ保存できるAI側の連携。
- レポート生成: Python 3.10以上。追加Pythonパッケージは不要です。
- 補助スクリプトからのPRコメント: github.comへ認証した `gh`。
- 画像投稿: GitHubのファイル添付を操作できるブラウザ機能、または利用者が指定した画像保存先。**補助スクリプトには画像アップロード機能がありません。**

既定のBeforeはPRのheadと取得時点のマージ先の共通祖先です。現在のmainを指定すればそのコミットを使います。前後を専用worktree・別portで起動し、同じ状態を撮影します。新規画面には「Beforeに存在しない」と記録します。

画像ホストや認証が足りない場合も、できたところまでの証拠を残し、未確認/未掲載を明示します。単なるコードレビュー、完全な回帰検出、pixel diff、CI連携、実Safari専用driver、外部画像ホスト運営は初版の対象外です。

## 対応状況と限界

| 項目 | 現在の状態 |
| --- | --- |
| Codex + 実Chromeで起動・操作・撮影 | ローカルfixtureで検証済み |
| Markdown / HTML生成、PC/SP指定、認証設定検証 | 実装済み・自動テストあり |
| Claude Code | 接続手順あり。実操作は未検証 |
| GitHubコメントの作成・更新 | 実装済み・Fake APIで検証。実PR投稿は未検証 |
| 画像アップロード | 利用者のブラウザ添付機能または指定保存先を使用。同梱アップローダーなし |
| Safari | 実Safariの操作手段がある環境でのみ追加可能。実操作は未検証 |

画像比較の対象は記録した画面と状態だけです。AIによる対象選定には見落としの可能性があり、「差が見えない」ことは全画面・機能・セキュリティの安全性を保証しません。

ローカル結果の生成に、このプロジェクトが運営する外部サービスは不要です。補助スクリプト・生成HTMLには独自の解析/テレメトリー送信を実装していません。ただし、利用するAIホスト・ブラウザ連携・対象アプリ・GitHub・指定画像ホストの通信やデータ取扱いはそれぞれの仕様に従います。認証値や実顧客データを成果物へ含めないでください。

## 更新

シンボリックリンクで導入した場合は、clone先を更新します。

```bash
git -C ~/src/pr-visual-review pull --ff-only
```

ローカルで改修している場合は差分を確認し、競合や変更を強制破棄しないでください。同じ実体を参照する別セッションにもファイルの変更が反映されます。既に手順を読み込んだセッションには「SKILL.mdと参照ファイルをディスクから読み直して」と依頼してください。別マシンのcloneやコピー配置は別途更新が必要です。

## 同梱内容

```text
pr-visual-review/
  SKILL.md                 共通の実行手順
  agents/openai.yaml       Codex UIメタデータ
  references/              環境、接続、認証、保存形式、PR掲載手順
  templates/report.json    未確認状態から始める記録テンプレート
  templates/auth.example.json  ログイン設定の例（秘密値なし）
  scripts/review.py         Markdown / HTML生成・所有コメントの更新
  scripts/auth_config.py    ログイン設定の形式検証
  assets/report.css        HTML用の共通表示
tests/                     投稿と証拠記録の境界を検証
examples/                  検証用の例と結果
```

スクリプト単体でブラウザ検証が完了することはありません。使い方は `python3 pr-visual-review/scripts/review.py --help`、詳細は [保存形式](pr-visual-review/references/report-format.md) と [PR掲載](pr-visual-review/references/publishing.md) を参照してください。

## 開発・検証

```bash
python3 -m unittest discover -s tests -v
```

投稿のテストはFake APIを使用し、実GitHubへは書き込みません。実ブラウザ・実PRでの検証範囲は [検証記録](examples/validation.md) に区別して残します。単体テストの成功を実PR掲載の成功とみなしません。

不具合報告・改善提案・PRは [CONTRIBUTING.md](CONTRIBUTING.md) を参照してください。初期版のため、特にブラウザ連携と実PR投稿の再現可能な検証報告を募集しています。

## License

[MIT](LICENSE)。
