<!-- pr-visual-review:v1 repo=example/local-fixture pr=1 -->
## PR Visual Review

対象: example/local-fixture #1

| Before commit | After commit | 比較元 |
| --- | --- | --- |
| `080006e935a661ac2f186ff63d27a91075d2fedd` | `b5c0016f0aa29d746a0f84dd1b13ae3607a67863` | merge-base |

撮影日時: 2026-10-07T06:53:18+09:00

ブラウザ: Google Chrome（インストール版154.0.8037.98、実行中versionは未照合）

条件: viewport 1551x1806 CSS px; DPR 1.100000023841858; locale ja; Asia/Tokyo; macOS 26.6.2; 同じChrome sessionと既定zoom; scroll top; メール通知オフの固定fixture; animationなし

記載した画面・状態だけを確認しています。全画面の回帰がないことは保証しません。

### ローカルfixture: 通知設定モーダル

画面: /

選定根拠: tests/smoke\_server.pyが作成した2つのGitコミット。index.htmlの.actions gapだけを0pxから24pxへ変更。実PRではありません。

ブラウザ: Google Chrome（インストール版154.0.8037.98、実行中versionは未照合）

条件: viewport 1551x1806 CSS px; DPR 1.100000023841858; locale ja; Asia/Tokyo; macOS 26.6.2; 同じChrome sessionと既定zoom; scroll top; メール通知オフの固定fixture; animationなし

操作: Before http://127.0.0.1:56186 と After http://127.0.0.1:56188 をそれぞれ開く → 通知設定を編集をクリック → モーダルと2つのボタンが表示されたことを確認 → 同じviewportで全体を撮影。ツールclip x=570,y=840,width=565,height=310でモーダル全体の拡大画像も取得。保存画像を開いて欠けがないことを確認

| Before | After |
| --- | --- |
| ![Before](<images/before.jpg>)<br>[変更箇所の拡大](<images/before-detail.jpg>) | ![After](<images/after.jpg>)<br>[変更箇所の拡大](<images/after-detail.jpg>) |

**意図した変更を確認**: Beforeはキャンセルと保存の境界が接しています。Afterは両ボタンの間に間隔があり、モーダル内の見出し・本文も表示されています。画像を目視確認しました。

### 未確認事項・制約

- これはローカルで作成した検証用fixtureです。実GitHub PRの解析・画像アップロード・コメント投稿は実施していません。
- Claude Codeでの実操作、Safari、認証が必要な実アプリ、モバイル実撮影は未実施です。
- Chromeの実行中versionと数値zoomは未照合です。前後で表示されたviewportとDPRの一致を確認しました。
