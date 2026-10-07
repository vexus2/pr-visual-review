# Codex adapter

1. セッションで提供されているブラウザ・GitHub・シェル能力を確認します。ツール名を推測して呼び出しません。接続済みのブラウザがなければ、その環境のブラウザ連携設定を案内し、差分解析・計画までは続けます。
2. `mcp__cua_repl` がある場合、ツールの初回呼び出し規則に従って Chrome を選択し、返された API documentation を読んで操作します。現在のページ/DOM/accessibility tree に基づいて遷移・クリックします。古い selector や座標を仮定しません。
3. ブラウザが実際の Google Chrome か確認します。Codex 内蔵ブラウザを Chrome として表示しません。スクリーンショット保存、viewport設定、ファイル添付は、そのセッションの API が提供する機能だけを使います。設定できない条件は実測・記録します。
4. まず1枚のスクリーンショットを専用runディレクトリへ保存し、ファイルの実在と内容を開いて確認します。ツール内の画像表示だけでローカル保存できたと報告しません。返された画像/保存パスを使い、スクリーンショット取得を別の非公開APIで代替しません。
5. 保存 API がない場合、文書化された画像 export があるか確認します。なければファイル取得を未完了と報告します。公開画像を捏造したり、スクリーンショットに見せかけたHTML再描画をしません。
6. PRへの添付は publishing.md の条件で行います。GitHubページでのfile input操作が能力として存在する場合だけ使います。UI操作が必要な場合はセッションの computer-use 指示を優先します。

ブラウザを操作するために生成されたPlaywrightテストを要求しません。既存のブラウザツールの内部実装がPlaywrightを使用することは、このスキルのテスト依存を意味しません。

Codexアプリで実PRを確認する依頼なら、提供されているPR添付ツールでそのPRを現在のチャットへ関連付けます。これはGitHubへの画像投稿とは別です。最終報告のローカルファイルリンクには絶対パスを使います。

このSkillはプラグインとして導入します。READMEの `codex plugin marketplace add` / `codex plugin add` の手順に従い、呼び出し名は `$pr-visual-review` です。本文中の `<skill-dir>` は、プラグインキャッシュ内の `skills/pr-visual-review/` を指します。配置と探索の仕様は [OpenAI公式プラグイン文書](https://developers.openai.com/plugins/build/plugins) と [スキル文書](https://developers.openai.com/codex/skills) に従い、特定の個人環境のパスを共有スキルへ埋め込みません。
