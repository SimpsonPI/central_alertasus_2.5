import asyncio
from telegram import Bot
import os
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

async def testar():
    bot = Bot(token=TOKEN)
    me = await bot.get_me()
    print(f"✅ Bot conectado: @{me.username}")

asyncio.run(testar())