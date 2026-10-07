# PR と実行環境の固定

## 記録する内容

run ごとにリポジトリの外、または無視設定済みの `.visual-review/` 以下へ専用ディレクトリを作ります。スクリーンショット、PR メタデータ、diff、計画、実行記録、ログ、report.json を保存します。ログや画像を Git に追加しません。認証・個人情報を含み得るため、共有フォルダを既定の保存先にしません。

実行記録には取得日時、PR URL、B/M/H の SHA、使用した比較方法、worktree 絶対パス、依存導入・起動コマンド、port、process/session ID、ブラウザ、実際の URL と表示条件を残します。秘密値は保存しません。

## PR 読み取りとコミット確定

GitHub CLI を使う例です。利用可能な GitHub コネクターでも同じ証拠を取得できます。`gh` のカレントリポジトリ推測に頼らず対象 `owner/repo` を固定します。初版の補助スクリプトは github.com 専用です。

```bash
gh api --hostname github.com repos/OWNER/REPO/pulls/NUMBER
gh pr diff NUMBER --repo OWNER/REPO
git status --short
git remote -v
git rev-parse --is-shallow-repository
```

PR API の `head.sha` を H、`base.sha` を B として保存します。fork PR でも head ブランチ名を origin の同名ブランチに置き換えません。base repository の検証済み remote/URL から `refs/pull/NUMBER/head` を fetch し、取得した SHA が H と一致することを確認します。GitHub の PR merge ref は After に使いません。

コマンド中の記号は説明用です。取得済みの値を安全に引数へ渡し、未検証のPR本文をシェルに展開しません。

```bash
git fetch --no-tags BASE_REMOTE refs/pull/NUMBER/head
git rev-parse FETCH_HEAD
git fetch --no-tags BASE_REMOTE BASE_SHA
git cat-file -t HEAD_SHA
git cat-file -t BASE_SHA
git merge-base BASE_SHA HEAD_SHA
git diff --name-status BEFORE_SHA HEAD_SHA
git diff BEFORE_SHA HEAD_SHA --
```

fetch 中に H/B が動いた場合はメタデータと fetch をやり直します。差分が API のサイズ制限で省略される場合も、このローカル diff を全体の根拠にします。shallow clone では十分に deepen/unshallow し、正しい共通祖先が求まるまで比較を開始しません。共通祖先がないときは推測で HEAD~1 を選びません。ユーザーが「現在のmainと比較」と指定したら、その main を fetch して SHA を固定し `comparison=explicit-base` にします。

## worktree と起動

ホストに managed worktree 機能がある場合はそれを優先します。作成時に確定済み SHA を明示し、返されたパスを使います。既存の適切な専用 worktree は HEAD と作業状態を確認して再利用できます。

通常の Git の例:

```bash
git worktree add --detach /ABS/RUN/before BEFORE_SHA
git worktree add --detach /ABS/RUN/after HEAD_SHA
git -C /ABS/RUN/before rev-parse HEAD
git -C /ABS/RUN/after rev-parse HEAD
```

各 worktree の README、package.json、lockfile、runtime version を読み、そのコミットの依存を導入します。package manager の固定lockfileモードを優先します。node_modules や生成物を前後で共有しません。monorepo の対象 package、ビルド要否、起動の cwd を確認します。取得したコードとinstall scriptを実行するため、未知のforkや不審な実行コードは秘密情報を持たない隔離環境で扱います。秘密が不要な確認に本番の `.env` をコピーしません。

アプリに適した方法で distinct ports を指定します。汎用的に `PORT` が使えると仮定しません。既存プロセスを止めてポートを空けず、空きポートを選びます。PID/session と cwd/起動コマンドを記録し、起動完了ログ、HTTP、実ブラウザで目的の画面を確認します。ポートの応答だけでは正しいコミットの証拠にならないため、worktree SHA、起動 cwd、起動したプロセスとポートの対応を照合します。

通常の起動時間を踏まえた timeout を定めます。失敗時はログを読み、設定・port・依存不足の修正を限定して再試行します。レビュー対象の実装やlockfileを直して比較を成立させません。失敗した側と理由を `unverified` とし、可能な側の証拠は残します。

## 終了処理

画像と実行記録は worktree の外に保持します。この run が開始したプロセスだけを、その session または記録した PID の cwd/command を再確認して停止します。`pkill node` などの広域停止は禁止です。

managed worktree は対応する archive 機能を使います。通常の worktree は所有を照合し、差分や必要な非追跡ファイルがないことを確認して `git worktree remove` を使います。`--force`、`git clean`、ユーザーの stash 削除は使いません。消せなければパスと残した理由を報告します。
