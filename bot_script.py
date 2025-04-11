import threading
import os
import discord
from dotenv import load_dotenv
from discord.ext import commands
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from flask import Flask

app = Flask(__name__)

load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
PORT = int(os.getenv("PORT", 8080))

@app.route("/")
def index():
    return "OK", 200

intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

scheduler = AsyncIOScheduler()

DAY_MAPPING = {
    "日": "sun",
    "月": "mon",
    "火": "tue",
    "水": "wed",
    "木": "thu",
    "金": "fri",
    "土": "sat"
}

class ScheduleModal(discord.ui.Modal, title="スケジュール通知の設定"):
    day = discord.ui.TextInput(
        label="曜日 (例：月曜日、火曜日、...)",
        placeholder="例：火曜日",
        required=True,
        max_length=10
    )
    time = discord.ui.TextInput(
        label="時間 (24時間形式 HH:MM)",
        placeholder="例：14:30",
        required=True,
        max_length=5
    )
    content = discord.ui.TextInput(
        label="通知する内容",
        style=discord.TextStyle.long,
        placeholder="例えば、毎週の定例ミーティング開始のお知らせなど",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        day_input = self.day.value.strip()
        day_key = day_input[0]
        if day_key not in DAY_MAPPING:
            await interaction.response.send_message(
                "入力された曜日が無効です。最初の文字が「日」「月」「火」「水」「木」「金」「土」のいずれかであるか確認してください。",
                ephemeral=True
            )
            return

        try:
            hour_str, minute_str = self.time.value.strip().split(":")
            hour = int(hour_str)
            minute = int(minute_str)
            if not (0 <= hour < 24 and 0 <= minute < 60):
                raise ValueError("時間の値が範囲外です")
        except Exception:
            await interaction.response.send_message(
                "時間の形式が正しくありません。HH:MM形式で入力してください。",
                ephemeral=True
            )
            return

        message_content = self.content.value.strip()
        cron_day = DAY_MAPPING[day_key]

        scheduler.add_job(
            send_notification,
            CronTrigger(day_of_week=cron_day, hour=hour, minute=minute),
            args=[interaction.channel.id, message_content]
        )
        await interaction.response.send_message("スケジュールされた通知が設定されました。", ephemeral=True)

async def send_notification(channel_id: int, content: str):
    """指定のチャンネルへ通知を送る非同期関数"""
    channel = bot.get_channel(channel_id)
    if channel and isinstance(channel, discord.TextChannel):
        await channel.send(content)

@bot.slash_command(
    name="schedule",
    description="指定した曜日、時刻にメッセージを通知するスケジュールを設定します。"
)
async def schedule(interaction: discord.Interaction):
    modal = ScheduleModal()
    await interaction.response.send_modal(modal)

@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    scheduler.start()

def run_discord_bot():
    bot.run(DISCORD_BOT_TOKEN)

if __name__ == "__main__":
    # Discord Bot を別スレッドで起動
    discord_thread = threading.Thread(target=run_discord_bot)
    discord_thread.start()

    # Flask アプリをメインスレッドで起動
    app.run(host="0.0.0.0", port=PORT)
