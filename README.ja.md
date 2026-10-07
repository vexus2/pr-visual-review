# PR Visual Review

[English](README.md) · 日本語

**PRを渡すと、AIが変更前後の画面とレビュー結果をまとめます。**

Codex / Claude Code向けのプラグインです。レビュー用Skillと補助スクリプトを同梱しています。

Codex / Claude Codeが差分から確認対象を選び、前後をローカルで起動・撮影します。スクリーンショット、所見、未確認事項を記録したレポートが成果物です。

## 依頼からレビュー結果まで

**1. 確認したいPRと範囲を伝えます。**

```text
$pr-visual-review PR #123をPCとSP（375px）で確認して。
追加された通知設定と、保存後の表示を確認してください。
レポートは英語で、まずはローカル保存だけ。
```

**2. AIが差分から対象画面を選び、前後を起動・撮影します。**

設定画面を特定し、別worktreeで変更前後を起動します。同じ画面幅・データで比較するため、毎回Playwrightテストを用意する必要はありません。

**3. 生成されたレポートで結果を確認します。**

![標準レポート: PCの追加表示、SPの問題1件、未確認の状態1件](examples/demo/images/report-overview.jpg)

この公開デモは、SPの崩れを意図的に含めた小さなローカルアプリです。実Chromeで撮影し、同梱rendererでレポートを生成しました。PR #123は説明用の識別子で、実GitHub PRではありません。

| 結果 | デモで確認した内容 |
| --- | --- |
| 意図した変更 | PCではメール通知の設定欄が追加されています |
| 要対応 | SPではフォームが画面より広くなり、保存ボタンが画面外に出ています |
| 未確認 | デモにbackendがないため、保存後の成功表示は確認できません |

### 差だけでなく、問題と根拠が分かる

Beforeは375px内に収まっています。Afterはページ幅が616pxになり、保存ボタンの左端が画面幅を超えます。レポートでは、意図した通知欄の追加と、この崩れを分けて記録します。

| Before：保存ボタンが見える | After：保存ボタンが画面外 |
| --- | --- |
| ![375pxのBefore](examples/demo/annotated/sp-settings-before-5f6ac524a6bc9878.png) | ![375pxのAfter](examples/demo/annotated/sp-settings-after-a8d1362c51f45923.png) |

青枠は変更、赤枠は問題、灰色枠はBeforeの参照箇所です。番号と説明が対応しています。AIが画像を確認して領域を選ぶ方式で、ピクセル差分の自動検出ではありません。原画像も残しています：[Before](examples/demo/images/sp-before.jpg) · [After](examples/demo/images/sp-after.jpg)。

[レポートを見る](examples/demo/report.md) · [デモの再現方法](examples/demo/README.md) · [検証範囲](examples/validation.md)

## プラグインの導入

### Codex

Codex CLIを使えるターミナルで実行します。

```bash
codex plugin marketplace add vexus2/pr-visual-review
codex plugin add pr-visual-review@pr-visual-review-marketplace
```

新しいCodexセッションを開き、プラグイン選択画面がある場合は **PR Visual Review** を選んでPRの確認を依頼します。同梱Skillの名前は `pr-visual-review` です。

### Claude Code

ターミナルで実行します。

```bash
claude plugin marketplace add vexus2/pr-visual-review
claude plugin install pr-visual-review@pr-visual-review-marketplace
```

新しいセッションを開くか `/reload-plugins` を実行し、次のように呼び出します。

```text
/pr-visual-review:pr-visual-review PR #123をPCとSPで確認して。ローカル保存だけ。
```

以下の依頼例はCodexの `$pr-visual-review` 表記です。Claude Codeでは上の名前付きコマンドか、「PR Visual Reviewで確認して」という自然言語の依頼を使います。

### 必要な環境

プラグインは手順と補助コードをまとめたものです。ブラウザ接続、Python、対象アプリの実行環境は導入されません。Git、Python **3.10以上**、アプリの依存関係、スクリーンショットを保存できるブラウザ連携が必要です。注釈PNGの書出しには任意のPillow依存を使います。HooksやMCPサーバーは同梱していません。

初版のパッケージ検証対象はCodex CLI **0.158.0**、Claude Code **2.1.284**です。古いクライアントではコマンドが使えない場合があります。公開リポジトリから配布する独自カタログであり、各社の公式ディレクトリへの掲載を意味しません。Windowsでの動作は未検証です。

<details>
<summary>すでにSkill単体で使っている場合</summary>

元のSkillディレクトリと既存の開発用リンクは維持しています。呼び出し先を一つにしたい場合は、Skill単体版とプラグイン版を同時に有効にしないでください。独自の変更を保存してから移行します。プラグインのインストールだけで旧版が自動削除されることはありません。

プラグイン非対応の環境では、従来の方法も使えます。

```bash
npx skills add vexus2/pr-visual-review --skill pr-visual-review
```

こちらは [skills CLI](https://github.com/vercel-labs/skills) の管理対象で、プラグインの更新とは別です。検証したインストーラー1.7.1にはNode.js 22.20.0以上が必要です。

</details>

## 使い方

```text
$pr-visual-review PR #123 の画面変更を確認して。
$pr-visual-review PR #123 をSPのみ375px幅で確認して。ローカル保存だけ。
$pr-visual-review PR #123 をPCのみ確認して。
$pr-visual-review PR #123 をPCとSPの両方で確認して。
$pr-visual-review https://github.com/owner/repo/pull/123 の変更前後のスクショをPRに貼って。
```

Claude Codeのプラグイン版では `/pr-visual-review:pr-visual-review` を使用できます。通常の自然言語依頼でも内容が一致すればスキルの選択対象になります。

「確認して」はローカル保存、「PRに貼って」は画像添付とPRコメントまでが対象です。「PCのみ」「SPのみ」「両方」を指定できます。対象外の端末は撮影せず、未確認件数にも足しません。SPはブラウザのスマホ幅での確認で、実機・タッチ操作の検証とは区別します。

幅を指定すればそれを優先します。指定のないサイズはプロジェクトの既定値、なければPC 1280×1000 / SP 390×844 CSS pxです。端末指定自体がなければPCのみで進め、開始時に範囲を伝えます。「スマホ表示も」は現在の範囲にSPを追加し、「PCのみ」への変更なら以前のSP結果を持ち越しません。「Safariも」は実Safariを操作できる場合だけ実施します。WebKitをSafariと表示しません。

レポートは英語・日本語を指定できます。report.jsonの `language` を `en` / `ja` にすると見出しや判定ラベルが切り替わります（省略時は従来の日本語）。所見本文は自動翻訳されません。

成果物は `report.json`・`report.md`・`report.html` と画像です。変更箇所とUIの問題を枠・番号で示せます。原画像は変更せず、HTMLでは枠を重ね、MarkdownやPRでは別に書き出した注釈付きPNGを使います。同じJSONから標準のHTMLを生成するため、セッションごとに独自のHTML生成コードを書く必要はありません。「今回発生」「今回悪化」「既存」「因果未確定」と「PRで要対応」「任意改善」「要調査」を分けて表示します。既存の横スクロールや通常の折り返しを、そのまま今回のPRの必須修正とは扱いません。

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
- レポート生成: Python 3.10以上。HTMLの注釈表示は追加パッケージ不要です。注釈付きPNGの書出しのみPillowを使います。
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

## 注釈付きPNGの書き出し

```bash
python3 -m pip install -r /ABS/SKILL/requirements-annotations.txt
python3 /ABS/SKILL/scripts/review.py annotate /ABS/RUN/report.json --out /ABS/RUN/report.annotated.json
python3 /ABS/SKILL/scripts/review.py render /ABS/RUN/report.annotated.json > /ABS/RUN/report.md
```

原画像と注釈付きPNGをそれぞれアップロードし、投稿にも派生JSONを使います。原画像や座標を変更した場合は、古いPNGを使わず再出力が必要です。PillowがなくてもHTMLの注釈は表示できますが、必要なPNGやURLがない状態では注釈付きPR投稿を止めます。[注釈の設定と手順](pr-visual-review/references/annotations.md)を参照してください。

## プラグインの更新

### Claude Code：自動更新を有効にする場合

`/plugin` → **Marketplaces** → **pr-visual-review-marketplace** → **Enable auto-update** を選びます。第三者のカタログは初期状態では自動更新が無効で、配布者側から有効にはできません。

更新後、現在のセッションで使うには `/reload-plugins` を実行します。新しいセッションでは更新後の内容が読み込まれます。手動更新する場合は次のコマンドを使います。

```bash
claude plugin marketplace update pr-visual-review-marketplace
claude plugin update pr-visual-review@pr-visual-review-marketplace
```

### Codex

カタログを更新し、その時点のプラグインをインストールします。

```bash
codex plugin marketplace upgrade pr-visual-review-marketplace
codex plugin add pr-visual-review@pr-visual-review-marketplace
```

更新後は新しいセッションを開いてください。バックグラウンドでの自動更新時期はクライアントに依存するため、このリポジトリでは保証していません。リリース時はプラグインのバージョンを上げます。[CHANGELOG.md](CHANGELOG.md)に記録します。

<details>
<summary>Skill単体版の更新</summary>

skills CLIで導入した場合は対象プロジェクトで `npx skills update pr-visual-review --project`、ユーザー共通配置なら `--global` を使います。手動コピーやCodexのskill-installerで配置したものは、その方法で新版へ置き換えます。プラグインの更新とは別です。

</details>

## プラグインを開発する場合

改修する場合はリポジトリをcloneします。

```bash
git clone https://github.com/vexus2/pr-visual-review.git
cd pr-visual-review
claude --plugin-dir .
```

Codexでは `codex plugin marketplace add .` でcheckoutをローカルカタログとして登録できます。同じカタログ名のローカル版とGitHub版は同時に登録せず、切替やpullの前にローカルの変更を保存してください。

Skillの実体は `pr-visual-review/` に残し、プラグインの `skills/pr-visual-review/` から内部リンクで参照します。公開時の手順は [プラグインの保守](docs/plugin-maintenance.md) を参照してください。

## 同梱内容

```text
plugin.json                共通プラグイン定義
.codex-plugin/             Codex用定義
.claude-plugin/            Claude Code用定義とカタログ
.agents/plugins/           Codex用カタログ
skills/pr-visual-review/   Skillの実体への内部リンク
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
