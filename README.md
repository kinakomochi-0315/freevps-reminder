# freevps-reminder

無料VPS（例: Xserver VPS など）の更新期限をDiscordでリマインドする、シンプルなDiscord Botです。スラッシュコマンドでリマインダーの設定・確認・削除ができ、期日が近づくと指定されたチャンネルにメンション付きで通知します。

## 機能概要
- /vps set で契約日数と任意のオフセット（UTCの日時分ずれ）を指定して次回更新日を設定
- /vps show で現在の設定（次回更新日・契約期間）を表示
- /vps del で設定を削除
- 1時間おきの定期実行で、期限が近いユーザーに自動でリマインド

## 必要要件
- Discord Bot トークン
- Python 実行環境（uv により自動的に仮想環境・依存関係を管理）
- POSIX シェル（run.sh を使う場合）

## 依存関係
- discord.py（Discord APIクライアント）
- python-dotenv（.env から環境変数を読み込み）

注: 本リポジトリの pyproject.toml の依存関係は環境に合わせて調整してください。discord.py を利用する場合は、以下のように設定します。

```toml
[project]
dependencies = [
  "discord.py>=2.3.2",
  "python-dotenv>=1.0.0",
]
```

## クイックスタート
1) リポジトリをクローン

2) .env ファイルをプロジェクト直下に作成し、以下を設定
```
DISCORD_BOT_TOKEN=あなたのDiscordBotトークン
# 任意設定（省略可）
REMINDER_DATA_FILE=reminders.json        # リマインダー保存先（既定: reminders.json）
REMINDER_DAYS_BEFORE=1                   # 期限まで何日以内で通知するか（既定: 1）
```

3) 起動
- uv を使った簡単起動（推奨）:
  ```sh
  ./run.sh
  ```
- もしくは手動で:
  ```sh
  # uv を使用
  uv sync
  uv run python main.py

  # または標準の仮想環境／pip を使用
  python -m venv .venv
  . .venv/bin/activate
  pip install -U pip
  pip install discord.py python-dotenv
  python main.py
  ```

## 使い方（Discord内）
Bot をサーバーに招待し、任意のテキストチャンネルで以下のスラッシュコマンドを使用します。

- /vps set
  - 引数: contract_days（更新期間・日数）, offset（オフセット・UTC、任意、デフォルト0）
  - 例: 「/vps set contract_days:30 offset:0」
- /vps show
  - 現在の設定（次回更新日・更新期間）を表示
- /vps del
  - 現在の設定を削除

Bot は1時間ごとにリマインダーをチェックし、以下条件を満たした場合に通知します。
- 期限日までの日数が REMINDER_DAYS_BEFORE 以下
- 同じ日にすでに通知していない
- 設定時に記録された channel_id が有効

通知文にはメンションと次回更新日、ログインページ（例: Xserver）へのリンクが含まれます。

## データ保存
- 既定ではプロジェクト直下の reminders.json にユーザーごとの設定を保存します。
- .gitignore で reminders.json はコミット対象外になっています。必要に応じて REMINDER_DATA_FILE で保存先を変更できます。

## ファイル構成
- main.py: Bot 本体とコマンド、リマインド処理
- run.sh: uv を用いた起動スクリプト（uvが無い場合は自動インストールを試行）
- pyproject.toml: パッケージ設定（必要に応じて依存関係を調整）
- reminders.json: リマインダー保存用JSON（初回は空）
- uv.lock: uv のロックファイル

## セキュリティ注意
- .env には機密情報（トークン）を保存します。リポジトリにコミットしないでください。
- トークン漏えい防止のため、公開リポジトリでは必ず環境変数管理を徹底してください。

## トラブルシューティング
- Bot がオンラインにならない: DISCORD_BOT_TOKEN の値を再確認、Bot が正しくサーバーに招待・権限付与されているか確認
- スラッシュコマンドが出ない: 起動直後は同期に時間がかかる場合があります。on_ready で tree.sync を呼んでいますが、必要に応じて数分待機してください。
- 通知が来ない: REMINDER_DAYS_BEFORE の設定、channel_id がNoneでないか、Bot にチャンネルへの送信権限があるか確認

## ライセンス
- TODO: ライセンスを決定
