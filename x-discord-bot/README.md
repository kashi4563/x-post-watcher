# X公式ポスト検知Bot（GitHub Actions版）

ワンスヒューマン日本公式X（@OnceHuman_JP）の新規ポストを検知して、
Discordの「公式Xポスト」チャンネルに自動で貼るための仕組みです。

- VPSやサーバーは不要です。GitHubの無料の定期実行（GitHub Actions）を使います
- 15分おきにチェックします（GitHub側の都合で数分遅れることがあります）
- 返信ポストは通知しません（リポストは通知します）
- 初回実行時は「今の最新ポスト」を基準に登録するだけで、何も投稿されません。
  次に公式が新規ポストしたときから通知が始まります

## あなたの作業は4つだけです

1. Discordで「ウェブフック」を作る（貼り付け先の住所を作る）
2. X開発者登録をして「Bearer Token」を取る（読み取り用の鍵）
3. GitHubにリポジトリを作って、このファイル一式を入れる
4. GitHubに鍵2つを登録する（Secrets）

鍵やURLはすべてGitHubの「Secrets」という金庫に入れます。
コードやファイルの中には書かないので、リポジトリを公開（Public）にしても
他人からは見えません。

---

## 手順1: Discordでウェブフックを作る

1. Discordで「公式Xポスト」チャンネルを開く
2. チャンネルの歯車（チャンネルの編集）→「連携サービス」→「ウェブフック」
3. 「新しいウェブフック」を押す
4. 名前を「公式ポスト検知」などに変えて、「URLをコピー」を押す
5. コピーしたURLはメモ帳などに一時的に控えておく（このあと手順4で使います）

※ このURLを知っている人は誰でもそのチャンネルに投稿できてしまいます。
チャットやSNSに貼らないでください。

## 手順2: X開発者登録と Bearer Token の取得

1. ブラウザで https://console.x.com を開き、自分のXアカウントでログイン
   （旧案内の developer.x.com ではなく、今は console.x.com が登録画面です）
2. 「Developer Agreement（開発者規約）」に同意する
3. APIの用途を聞かれるので、英語で短く書く（例はモコの案内文を参照）
4. プロジェクトとアプリを作成する（アプリ名は自由。例: sabaonagi-x-notifier。
   他の人のアプリと同名は使えないので、被ったら数字を足す）
5. アプリの「Keys and Tokens」画面で「Bearer Token」を表示し、コピーして控える
   ※ Token は一度しか表示されません。チャット等に貼らず、自分だけが見える場所に保管してください
6. 料金は従量課金制です。「Billing」画面でカードを登録し、クレジットを購入する
   最初は $5 分で十分です（時期により、初回購入で $20 分の無料クレジットが
   付くキャンペーンをしている場合があります）

目安: 15分おきチェックで、同じポストへの課金は1日1回までのため、
公式アカウントの投稿数なら月 $1 前後（約150円）の見込みです。
クレジットが尽きると検知が止まり、GitHubから実行失敗のメールが届きます。

## 手順3: GitHubにリポジトリを作ってファイルを入れる

1. https://github.com でアカウントを作る（持っていればログイン）
2. 右上の「+」→「New repository」
   - 名前は自由（例: x-post-watcher）
   - 「Public」を選ぶ（無料の実行枠を気にしなくて済みます。鍵は手順4の金庫に入るので安全です）
   - 「Create repository」を押す
3. 作成したリポジトリの画面で「uploading an existing file」を押す
4. 配布された zip を展開し、中身すべて（.github フォルダごと）を
   ドラッグ＆ドロップしてアップロードし、「Commit changes」を押す

※ .github フォルダがアップロードできなかった場合は、
「Add file」→「Create new file」でファイル名に
`.github/workflows/check-x-posts.yml` と入力し、配布ファイルの中身を
貼り付けて保存してください。

## 手順4: GitHubに鍵を登録する（Secrets）

リポジトリの「Settings」→ 左メニューの「Secrets and variables」→「Actions」
→「New repository secret」を押し、以下を1つずつ登録します。

| 名前 | 値 |
| --- | --- |
| DISCORD_WEBHOOK_URL | 手順1でコピーしたURL |
| X_BEARER_TOKEN | 手順2でコピーした Bearer Token |
| X_USERNAMES | （任意）監視アカウント。空欄なら OnceHuman_JP のみ。追加する場合は `OnceHuman_JP,OnceHuman` のようにカンマ区切り |

## 手順5: テスト実行

1. リポジトリの「Actions」タブを開く
   （初めての場合「I understand my workflows, go ahead and enable them」を押す）
2. 左の「X post watcher」を選び、「Run workflow」→「Run workflow」
3. 1〜2分後、実行結果が緑のチェックになればOKです
   - 初回は基準登録だけなので、Discordには何も投稿されません（正常です）
   - 次に公式がポストしたら、15分程度でDiscordに届きます

### すぐに動作を見たい場合（任意）

1. リポジトリの `state.json` を開き、右上の鉛筆アイコンで編集
2. `"last_seen_id": "数字"` の数字を `0` に書き換えて保存（Commit）
3. 手順5と同じく「Run workflow」を実行
4. 直近の最大5件のポストがDiscordにまとめて届けば成功です

## 運用メモ

- **止めたいとき**: Actionsタブ →「X post watcher」→ 右上の「…」→「Disable workflow」
- **チェック間隔を変えたいとき**: `.github/workflows/check-x-posts.yml` の
  `cron: "*/15 * * * *"` の数字を変更（例: 30分おきは `*/30`）
- **state.json のコミットが増えていきます**が、これは仕様です
  （活動がないリポジトリは定期実行が自動で止められてしまうため、
  チェックのたびに状態を保存しています）

## うまくいかないとき（Actionsのログで確認）

- `HTTP 401` → Bearer Token が違う、または未登録
- `HTTP 402` → Xのクレジット不足。開発者コンソールでクレジットを追加
- `HTTP 403` → X開発者登録・アプリの権限まわりを確認
- Discord Webhook エラー `HTTP 404` → Webhook URL が違う、または削除されている
- 実行自体が始まらない → Actionsが有効化されているか、ファイルの置き場所
  （.github/workflows の中か）を確認

困ったら Actions の赤い×を開いた画面のスクリーンショットをモコに送ってください。
