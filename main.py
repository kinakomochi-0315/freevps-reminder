import datetime
import json
import os
from datetime import timedelta
from typing import Final, Optional
import sys

import discord
from discord.ext import tasks
from dotenv import load_dotenv
from rich.logging import RichHandler
import logging
load_dotenv()

# -------- ログ設定（Rich） --------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[RichHandler(rich_tracebacks=True, markup=True)]
)
logger = logging.getLogger("freevps-reminder")

intents = discord.Intents.default()
intents.reactions = True
bot = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(bot)

DISCORD_BOT_TOKEN: Final[str] = os.getenv("DISCORD_BOT_TOKEN")
REMINDER_DATA_FILE: Final[str] = os.getenv("REMINDER_DATA_FILE", "reminders.json")
REMINDER_DAYS_BEFORE: Final[int] = int(os.getenv("REMINDER_DAYS_BEFORE", "1"))


# -------- データ管理関数 --------

def load_reminders() -> dict:
    """リマインダー情報をJSONファイルから読み込む関数。ファイルが無い場合は空の辞書を返します。"""
    if not os.path.exists(REMINDER_DATA_FILE):
        logger.info("リマインダーファイルが存在しません。空のデータを返します。")
        return {}
    try:
        with open(REMINDER_DATA_FILE, "r") as f:
            data = json.load(f)
            logger.info("リマインダーデータを読み込みました。件数: %d", len(data))
            return data
    except Exception:
        logger.exception("リマインダーデータの読み込みに失敗しました。JSONの形式を確認してください。")
        return {}


def save_reminders(reminders: dict):
    """リマインダー情報をJSONファイルへ保存する関数。"""
    try:
        with open(REMINDER_DATA_FILE, "w") as f:
            json.dump(reminders, f)
        logger.info("リマインダーデータを保存しました。件数: %d", len(reminders))
    except Exception:
        logger.exception("リマインダーデータの保存に失敗しました。書き込み権限やディスク容量を確認してください。")


# -------- リマインダー管理コマンド --------

vps = discord.app_commands.Group(name="vps", description="VPSの更新リマインダーを管理できます")


@vps.command(name="set", description="リマインダーを設定します")
@discord.app_commands.describe(contract_days="更新期間（日数）", offset="次の更新日を前後に調整します",
                               next_deadline="次の更新日を直接指定します(yyyy-MM-dd)")
async def set_reminder(interaction: discord.Interaction, contract_days: int, offset: int = 0,
                       next_deadline: Optional[str] = None):
    """ユーザーのVPS更新リマインダーを設定するスラッシュコマンド。"""
    user_id = str(interaction.user.id)
    channel_id = str(interaction.channel.id) if interaction.channel else None

    if next_deadline:
        try:
            # 直接指定した日付を設定
            deadline_date = datetime.date.fromisoformat(next_deadline)
        except ValueError:
            logger.warning("不正な日付形式が指定されました。user_id=%s 入力=%s", user_id, next_deadline)
            await interaction.response.send_message("⚠️指定された日付が不正です。yyyy-MM-dd形式で入力してください。")
            return
    else:
        # リマインダーの日付を計算
        today = interaction.created_at.date()
        deadline_date = today + timedelta(days=(contract_days + offset))

    # リマインダーを保存›
    reminders = load_reminders()
    reminders[user_id] = {
        "channel_id": channel_id,
        "contract_days": contract_days,
        "deadline_date": deadline_date.isoformat(),
        "last_reminded": "1970-01-01",
        "reminder_message_id": None,
    }
    save_reminders(reminders)
    logger.info("リマインダーを設定しました。user_id=%s 次回更新日=%s 期間=%d日", user_id, deadline_date.isoformat(),
                contract_days)

    await interaction.response.send_message(
        f"リマインダーを設定しました。\n"
        f"**次回更新日** {deadline_date.isoformat()}"
    )


@vps.command(name="show", description="設定されているリマインダーを表示します")
async def show_reminders(interaction: discord.Interaction):
    """設定済みのリマインダー内容（次回更新日・更新期間）を返信するスラッシュコマンド。"""
    user_id = str(interaction.user.id)

    # リマインダーが設定されていない場合
    reminders = load_reminders()
    if user_id not in reminders.keys():
        logger.info("ユーザーにリマインダーは未設定です。user_id=%s", user_id)
        await interaction.response.send_message("リマインダーが設定されていません。")
        return

    # リマインダーの日付を表示
    reminder = reminders[user_id]
    logger.info("リマインダー情報を表示します。user_id=%s 締切=%s 期間=%s日", user_id, reminder['deadline_date'],
                reminder['contract_days'])
    await interaction.response.send_message(
        f"**次回更新日** {reminder['deadline_date']}\n"
        f"**更新期間** {reminder['contract_days']}日"
    )


@vps.command(name="del", description="設定されているリマインダーを削除します")
async def del_reminder(interaction: discord.Interaction):
    """設定されているユーザーのリマインダーを削除するスラッシュコマンド。"""
    user_id = str(interaction.user.id)

    # リマインダーが設定されていない場合
    reminders = load_reminders()
    if user_id not in reminders:
        logger.warning("削除要求がありましたが、リマインダーは未設定です。user_id=%s", user_id)
        await interaction.response.send_message("リマインダーが設定されていません。")
        return

    # リマインダーを削除
    del reminders[user_id]
    save_reminders(reminders)
    logger.info("リマインダーを削除しました。user_id=%s", user_id)

    await interaction.response.send_message("リマインダーを削除しました。")


async def send_reminder(user_id: str, channel_id: str, deadline_date: str) -> Optional[discord.Message]:
    """指定されたチャンネルに、ユーザー宛の更新期限リマインドメッセージを送信する関数。"""
    mention = f"<@{user_id}>"
    channel = bot.get_channel(int(channel_id))

    if not channel:
        logger.error("チャンネルが見つかりません。channel_id=%s", channel_id)
        return None

    try:
        message = await channel.send(
            f"{mention} ⚠️ **無料VPSの更新期限が近づいています！** ⚠️\n"
            f"**次回更新日** {deadline_date}\n"
            "ここからログインできます: [ログインページ](https://secure.xserver.ne.jp/xapanel/login/xvps/)"
            "-# 契約更新を行ったら、このメッセージにリアクションをつけてください。"
        )
        logger.info("リマインドメッセージを送信しました。user_id=%s channel_id=%s message_id=%s", user_id, channel_id,
                    message.id)
        return message
    except Exception:
        logger.exception("リマインドメッセージの送信に失敗しました。user_id=%s channel_id=%s", user_id, channel_id)
        return None


def should_send_reminder(deadline_date: str, last_reminded_date: str) -> bool:
    """指定されたユーザーのリマインドメッセージを送信するかどうかを判定する関数。"""
    today = datetime.date.today()
    deadline = datetime.date.fromisoformat(deadline_date)
    last_reminded = datetime.date.fromisoformat(last_reminded_date)

    # 期限が遠い場合はスキップ
    if (deadline - today).days > REMINDER_DAYS_BEFORE:
        logger.info("期限が遠いためスキップします。締切=%s 今日=%s しきい値=%d", deadline, today, REMINDER_DAYS_BEFORE)
        return False

    # 今日はもうリマインド済みならスキップ
    if last_reminded == today:
        logger.info("本日は既にリマインド済みのためスキップします。最終リマインド=%s", last_reminded)
        return False

    return True


# 1時間ごとにリマインダーをチェック
@tasks.loop(hours=1)
async def check_reminders():
    """1時間ごとに期限を確認し、必要に応じてリマインドを送信・日付更新する定期タスク。"""
    logger.info("定期チェックを開始します。")
    reminders = load_reminders()
    for user_id, reminder in reminders.items():
        try:
            if not should_send_reminder(reminder["deadline_date"], reminder["last_reminded"]):
                continue

            # チャンネルを検索
            channel_id = reminder["channel_id"]
            if not channel_id:
                logger.warning("チャンネルIDが未設定のためスキップします。user_id=%s", user_id)
                continue

            # チャンネルにリマインドメッセージを送信
            message = await send_reminder(user_id, channel_id, reminder["deadline_date"])

            if not message:
                logger.warning("メッセージ送信に失敗したためスキップします。user_id=%s", user_id)
                continue

            # 最後にリマインドした日付を更新
            reminders[user_id]["last_reminded"] = datetime.date.today().isoformat()
            reminders[user_id]["reminder_message_id"] = str(message.id)
            save_reminders(reminders)
            logger.info("リマインド後の状態を保存しました。user_id=%s", user_id)
        except Exception:
            logger.exception("定期チェック処理中にエラーが発生しました。user_id=%s", user_id)


@bot.event
async def on_reaction_add(reaction: discord.Reaction, user: discord.User):
    """リアクションが追加されたときに呼び出されるイベントハンドラー"""
    logger.info("リアクションが追加されました。user_id=%s message_id=%s", user.id, reaction.message.id)

    # BOTの場合はスキップ
    if user.bot:
        logger.warning("リアクションをつけたのがBOTだったためスキップします。")
        return

    # このbotによるメッセージに対するリアクションのみを受け付ける
    if not reaction.message.author.id == bot.user.id:
        logger.warning("このbotによるメッセージに対するリアクションではないのでスキップします。")
        return

    message_id = str(reaction.message.id)
    user_id = str(user.id)
    reminders = load_reminders()

    for reminder_user_id, reminder in reminders.items():
        # リマインドメッセージにリアクションが付いたら、リマインドを終了し更新期限を延長
        if message_id == reminder.get("reminder_message_id") and user_id == reminder_user_id:
            reminders[reminder_user_id]["reminder_message_id"] = None

            # 更新期限を更新
            contract_days: int = reminder["contract_days"]
            deadline_date: datetime.date = datetime.date.fromisoformat(reminder["deadline_date"])
            reminders[reminder_user_id]["deadline_date"] = (deadline_date + timedelta(days=contract_days)).isoformat()

            save_reminders(reminders)
            logger.info("リアクションを検知し、期限を延長しました。user_id=%s 新しい締切=%s", reminder_user_id,
                        reminders[reminder_user_id]["deadline_date"])


@bot.event
async def on_ready():
    """Bot起動時に呼び出されるイベントハンドラー。コマンド同期と定期タスク開始を行います。"""
    # 起動時に動作する処理
    logger.info("ログインしました: %s (ID: %s)", bot.user, bot.user.id)
    try:
        await tree.sync()
        logger.info("スラッシュコマンドを同期しました。")
    except Exception:
        logger.exception("スラッシュコマンドの同期に失敗しました。")

    # リマインダーチェックループを開始
    logger.info("リマインダーチェックループを開始します...")
    try:
        check_reminders.start()
    except RuntimeError:
        # 既に開始済みの場合は警告
        logger.warning("リマインダーチェックループは既に開始されています。")


# -------- 起動処理 --------
if __name__ == "__main__":
    tree.add_command(vps)
    if not DISCORD_BOT_TOKEN:
        logger.error("DISCORD_BOT_TOKEN が設定されていません。.env もしくは環境変数を確認してください。")
        sys.exit(1)
    bot.run(DISCORD_BOT_TOKEN)
