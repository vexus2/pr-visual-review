# Claude Code adapter

[公式Chrome連携](https://code.claude.com/docs/en/chrome) と、実行中のセッションに公開されているツールスキーマを確認します。連携が有効でない場合は設定を案内し、使えるふりをしません。起動フラグや拡張機能の導入は、その時点の公式説明と利用者の環境で確認します。

- タブ一覧/作成、画面やDOMの読み取り、クリック/入力、スクリーンショット、画像保存能力を確認します。
- 公式文書の screenshot `save_to_disk` が提供されるバージョンではその機能を使います。呼び出し後は必ず返されたパスの存在と画像内容を確認します。ツールが画面内に画像を返しただけなら保存完了ではありません。
- screenshot の export がない古い環境ではファイル取得を未完了とし、更新や利用可能な接続方法を案内します。非公開APIや未確認のツール名で補いません。
- ファイルアップロードは公式Chrome連携の能力が実際に提供される場合に利用できます。GitHubの投稿先と選んだ画像を確認してから実行します。添付完了とコメント投稿完了を別に確認します。
- 同じChromeでも別profile/sessionでは認証状態が異なります。ユーザーの普段のタブを閉じず、専用タブを使います。

基本の記録と出版契約は Codex と共通です。Chrome連携だけで `gh` 認証も利用できるとは仮定しません。`gh` がない場合はGitHub UIで同じmarker・投稿者・PR headを照合して投稿します。CLIがなくてもローカルreport生成はPythonで実行できます。

Skillの導入先は `~/.claude/skills/pr-visual-review/` または対象リポジトリの `.claude/skills/pr-visual-review/` です。[公式Skills文書](https://code.claude.com/docs/en/skills) を参照してください。
