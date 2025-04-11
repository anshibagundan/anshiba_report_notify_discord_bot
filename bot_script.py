import os
import threading
import discord
from discord.ext import commands
from flask import Flask

# Flask アプリの定義（ヘルスチェック用）
app = Flask(__name__)

@app.route('/')
def index():
    return 'OK', 200

def run_http_server():
    port = int(os.getenv("PORT", 8080))
    # Cloud Run では必ず "0.0.0.0" をバインドする必要があります
    app.run(host="0.0.0.0", port=port)

# Discord Bot の設定
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"Bot is ready as {bot.user}")

# Bot の例として簡単なコマンドを追加
@bot.command()
async def ping(ctx):
    await ctx.send("Pong!")

def main():
    # Flask サーバーを別スレッドで起動
    http_thread = threading.Thread(target=run_http_server)
    http_thread.start()
    # Discord Bot を起動（ここで永続的な接続を確立します）
    bot.run("YOUR_BOT_TOKEN")

if __name__ == "__main__":
    main()
