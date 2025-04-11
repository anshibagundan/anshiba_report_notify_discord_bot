import threading
import os
import discord
from dotenv import load_dotenv
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from flask import Flask

# Flask のセットアップ
app = Flask(__name__)

load_dotenv()

# 環境変数から各種情報を取得
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080))

# MySQLの接続情報（Cloud SQL パブリックIP接続の場合）
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASS", "password")
DB_NAME = os.getenv("DB_NAME", "anshiba_report_notify_discord_bot")
DB_HOST = os.getenv("DB_HOST", "35.192.14.165")
DB_PORT = os.getenv("DB_PORT", "3306")

# SQLAlchemyJobStore を利用してジョブ情報を MySQL に永続化
mysql_connection_string = f"mysql+mysqldb://{DB_USER}:{DB_PASS}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
jobstores = {
    'default': SQLAlchemyJobStore(url=mysql_connection_string)
}
scheduler = AsyncIOScheduler(jobstores=jobstores)

# Flask のルートエンドポイント
@app.route("/")
def index():
    return "OK", 200

# Discord Bot のセットアップ
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

DAY_MAPPING = {
    "日": "sun",
    "月": "mon",
    "火": "tue",
    "水": "wed",
    "木": "thu",
    "金": "fri",
    "土": "sat"
}

@bot.command(name="help_schedule")
async def help_schedule(ctx):
    """スケジュール機能の使い方を表示します"""
    help_text = """
レポートの提出期限やイベントのリマインダーなど、特定の曜日と時間にメッセージを送信するスケジュール機能を提供するbotです。
機能重要なタスクやイベントを忘れずに管理できます。

**スケジュールコマンドの使い方**

`!schedule <曜日> <時間> <メッセージ>`

**例：**
`!schedule 月 14:30 定例ミーティングの時間です`
`!schedule 金 18:00 今週の作業報告を提出してください`

**対応曜日：**
日、月、火、水、木、金、土

**時間形式：**
24時間形式（例：09:00、14:30、23:45）

※ !schedule コマンドを実行したチャンネルに定期的にメッセージが送信されます。

**スケジュール一覧の表示**

`!list_schedules`

現在設定されている全てのスケジュールを一覧表示します。


**スケジュールの削除**

`!remove_schedule <番号>`

一覧表示で確認した番号を指定して、特定のスケジュールを削除します。
番号は `!list_schedules` で表示されるリストの順番に対応しています。

**使い方の表示**
`!help_schedule`
スケジュール機能の使い方を表示します。

**新規機能を作成した場合**
master以外のブランチでPRを作成してください。
PRを作成する際は、以下のことを確認してください。
1. master以外のブランチで開発してください。PRのbaseはmasterにしてください。
2. コードはローカルで実行できることを確認してください。
3. PRを作成してください。
4. PRのレビューを依頼してください。(おそらく自動のはず)
5. PRのレビューが通ったら、masterにマージしてください。
6. masterにマージしたら、GitHub Actionsが自動でdocker buildを行い、GCP Artifact Registryにpushします。
7. GCP Artifact Registryにpushされ、Approveされ、masterにマージされるとGitHub Actionsが自動でGCP Cloud Runにデプロイします。


"""
    await ctx.send(help_text)

@bot.command(name="schedule")
async def schedule_command(ctx, day=None, time=None, *, message=None):
    """指定した曜日、時刻にメッセージを通知するスケジュールを設定します"""
    if day is None or time is None or message is None:
        await ctx.send("引数が不足しています。`!help_schedule` で使い方を確認してください。")
        return

    day_key = day[0]
    if day_key not in DAY_MAPPING:
        await ctx.send("入力された曜日が無効です。最初の文字が「日」「月」「火」「水」「木」「金」「土」のいずれかであることを確認してください。")
        return

    try:
        hour_str, minute_str = time.strip().split(":")
        hour = int(hour_str)
        minute = int(minute_str)
        if not (0 <= hour < 24 and 0 <= minute < 60):
            raise ValueError("時間の値が範囲外です")
    except Exception:
        await ctx.send("時間の形式が正しくありません。HH:MM形式で入力してください。")
        return

    cron_day = DAY_MAPPING[day_key]
    scheduler.add_job(
        send_notification,
        CronTrigger(day_of_week=cron_day, hour=hour, minute=minute, timezone="Asia/Tokyo"),
        args=[ctx.channel.id, message]
    )
    await ctx.send(f"{day}曜日 {time} にメッセージを送信するようスケジュールを設定しました。")

@bot.command(name="list_schedules")
async def list_schedules(ctx):
    """現在設定されているスケジュールを表示します"""
    jobs = scheduler.get_jobs()
    if not jobs:
        await ctx.send("現在設定されているスケジュールはありません。")
        return

    response = "**現在設定されているスケジュール**\n"
    for i, job in enumerate(jobs, 1):
        trigger = job.trigger
        args = job.args
        response += f"{i}. {trigger}: {args[1]}\n"

    await ctx.send(response)

@bot.command(name="remove_schedule")
async def remove_schedule(ctx, index: int = None):
    """スケジュールを削除します"""
    if index is None:
        await ctx.send("削除するスケジュール番号を指定してください。番号は `!list_schedules` で確認できます。")
        return

    jobs = scheduler.get_jobs()
    if not jobs:
        await ctx.send("現在設定されているスケジュールはありません。")
        return

    if index < 1 or index > len(jobs):
        await ctx.send(f"無効な番号です。1から{len(jobs)}の間で指定してください。")
        return

    job_to_remove = jobs[index - 1]
    job_to_remove.remove()
    await ctx.send(f"スケジュール {index} を削除しました。")

async def send_notification(channel_id: int, content: str):
    """指定のチャンネルへ通知を送る非同期関数"""
    channel = bot.get_channel(channel_id)
    if channel is None:
        channel = await bot.fetch_channel(channel_id)
    if channel:
        await channel.send(content)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    if not scheduler.running:
        scheduler.start()

def run_discord_bot():
    bot.run(DISCORD_BOT_TOKEN)

if __name__ == "__main__":
    discord_thread = threading.Thread(target=run_discord_bot)
    discord_thread.start()

    app.run(host="0.0.0.0", port=PORT)
