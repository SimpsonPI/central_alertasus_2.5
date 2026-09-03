import os
import asyncio
from dotenv import load_dotenv
from telegram import Bot, BotCommand

# Carrega as variáveis do .env
load_dotenv()

# Token do bot da Central
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

if not TOKEN:
    raise ValueError("❌ TELEGRAM_BOT_TOKEN não configurado no .env")

async def atualizar():
    bot = Bot(token=TOKEN)
    comandos = [
    BotCommand("start", "🚀 Iniciar Atendimento"),
    BotCommand("menu", "📋 Menu Principal"),
    BotCommand("atendimento", "👤 Atendimento Humanizado"),
    BotCommand("faq", "❓ Perguntas Frequentes (FAQ)"),
    BotCommand("chamados", "📋 Meus Chamados"),
    BotCommand("suporte", "💬 Falar com Atendente"),
    BotCommand("responder", "💬 Responder Chamado (Admin)"),
]
    await bot.set_my_commands(comandos)
    print("✅ Menu da Central VigiaSaúde atualizado com sucesso!")

asyncio.run(atualizar())