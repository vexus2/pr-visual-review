# OSS README調査とPR Visual Reviewへの提案

調査日: 2026-10-07 JST。下記リポジトリのGitHub APIとREADME本文を取得して確認しました。人気・導入効果の比較ではなく、READMEの構成を調べたものです。本文の記載を確認しただけで、各ツールの機能を実行検証したものではありません。

## 調査対象

| リポジトリ | READMEで確認した構成 | このSkillに採り入れる点 |
| --- | --- | --- |
| [vercel-labs/agent-browser](https://github.com/vercel-labs/agent-browser/blob/main/README.md) | 冒頭の一文、Installation、Requirements、Quick Start、Authentication、Security、Updating。AIへ渡す指示例も掲載 | 必要なブラウザ連携を明記し、最初の依頼文と更新手順を示す。認証の詳細は別文書へ |
| [obra/superpowers](https://github.com/obra/superpowers/blob/main/README.md) | How it works、エージェント別Installation、Basic Workflow、Contributing、Updating、License、telemetry説明 | Codex/Claude別導入、何を自動実行するか、更新方法、データ取扱いを説明する |
| [browser-use/browser-use](https://github.com/browser-use/browser-use/blob/main/README.md) | 冒頭にデモ、Which Browser Use do I need?、用途別Quickstart、FAQ。クラウド・CLI・Pythonを区別 | 最初に実画像で結果を示す。Skill・補助スクリプト・必要なブラウザ接続の役割を区別する |
| [reg-viz/reg-suit](https://github.com/reg-viz/reg-suit/blob/master/README.md) | Compare Images / Store Snapshots / Work Everywhereの説明、短いGetting Started、実例、設定、Plugins、Contribute、License | 撮影・比較・画像保存・PR通知を分けて説明し、ローカル例と動かし方を用意する |
| [anthropics/skills](https://github.com/anthropics/skills/blob/main/README.md) | Skillの定義、フォルダ構成、環境別の使い方、最小SKILL例、環境差の注意、各ライセンスの説明 | SKILL.mdだけでなくフォルダ全体を導入すること、環境ごとの検証範囲を明記する |

前4件は取得時点のGitHub metadata上でApache-2.0またはMITでした。anthropics/skillsは、README自身がApache-2.0のOSS部分とsource-availableの文書Skillを区別しています。リポジトリ全体を一括でOSSと扱わず、Skill配布の参考例として含めています。reg-suitは新規プロジェクトではありませんが、用途が近く現在も更新されている比較対象です。

## 推奨するREADMEの順序

1. **何ができるかを1〜2文で。** 「PRを渡すとAIが確認対象を選び、前後の実画面と所見を残す」。完全な回帰検出や全環境の自動起動を約束しない。
2. **Before/Afterの実画像と一言の依頼例。** サンプルは公開可能なfixtureを使い、実PR成功例と混同させない。結果を理解してから導入へ進める。
3. **最短の導入と最初の実行。** clone → CodexまたはClaudeへ配置 → ローカル確認の一言。初回は外部投稿を不要にする。
4. **必須条件。** Git、Python 3.10+、対象アプリruntime、実ブラウザ操作・画像export。PR投稿だけに必要なghや画像upload能力を分離する。
5. **何をするか。** PR差分解析 → SHA固定 → worktree起動 → 同一状態の撮影 → JSON/Markdown/HTML → 依頼時だけPR投稿。
6. **使い方の分岐。** PCのみ/SPのみ/両方、幅指定、認証方式、ローカル保存/PR投稿。網羅的なschemaはreferencesに置く。
7. **成果物と判定の意味。** 新規・悪化・既存・因果未確定、必須・任意・要調査を区別する。0件をマージ許可と表現しない。
8. **対応表・既知の制約。** Codex+Chromeの実検証、Claude/Safariの未検証、画像uploadは別機能、PR投稿はFake API検証まで、を一目で分かるようにする。
9. **認証・データの扱い。** 値を含めない参照方式、外部投稿が発生する条件、ホスト側通信との境界。根拠なく「完全ローカル」「一切外部送信なし」と書かない。
10. **更新、困ったとき、貢献、License。** symlinkとコピーの違い、再読み込み、最小再現、テストコマンド、MITへのリンク。

## 今回READMEに反映した内容

- 初回は短い英語説明を補足し、その後README.mdを英語、README.ja.mdを日本語に分離しました。
- 公開可能なローカルfixtureのBefore/Afterと依頼文を冒頭へ置きました。
- 実際の公開URLでcloneできる導入手順と、symlink配置・更新・コピーとの差を記載しました。
- 実装済みと実環境検証済みを分けた対応表を追加しました。
- テレメトリーとAIホスト/対象アプリの通信の境界を説明しました。
- CONTRIBUTING.mdとMIT LICENSEを追加しました。

## 次に検討する内容

優先度順です。現時点で実装・検証したと読み取れる表現は避けます。

1. **英語README + 日本語版への分離。対応済み。** README.mdを英語、README.ja.mdを日本語として相互リンクし、両方に同じ対応表・制約を持たせました。
2. **実PRでの画像添付からコメント更新までの公開デモ。** 合成fixtureの現在の例に加え、専用デモrepoで検証できた後に掲載します。
3. **CIの状態バッジ。** 実際のworkflowを設定して成功を確認してから掲載します。今回CIは追加していません。
4. **報告例の短いGIF/動画。** 実操作を収録できたら追加します。静止画が既に目的を伝えるため、装飾的な動画を先に作る必要はありません。
5. **Issue template / SECURITY.md / CHANGELOG。** 利用者が増える段階で、運用できる受付経路とリリース管理を決めて追加します。

既存ツールの実績バッジ・ベンチマーク・クラウドサービスへの導線を、そのまま模倣する必要はありません。初期のSkillでは「何を依頼すれば、何が保存され、どこまで確認できたか」が最も重要です。
