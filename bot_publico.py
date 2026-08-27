import telebot
from telebot import types
from supabase import create_client, Client
import os
from dotenv import load_dotenv

load_dotenv()

# ====== VARIÁVEIS ======
BOT_TOKEN = os.getenv("BOT_PUBLICO_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
LINK_PRINCIPAL = os.getenv("BOT_PRINCIPAL_LINK", "https://t.me/meu_atendimento_123_bot")

bot = telebot.TeleBot(BOT_TOKEN)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
em_atendimento = {}

# ==================== /START ====================
@bot.message_handler(commands=['start'])
def inicio(msg):
    uid = msg.from_user.id
    menu = types.ReplyKeyboardMarkup(resize_keyboard=True)
    menu.row("/ajuda", "/suporte")
    menu.row("/planos", "/cadastrar")
    menu.row("/gerenciar", "/sobre")

    bot.send_message(msg.chat.id,
f"""🙋‍♂️ *Central de Atendimento AlertaSUS 2.5*

Seu ID único: `{uid}`

Aqui você encontra orientações, dúvidas frequentes e suporte para o sistema de acompanhamento de regulações de exames e consultas na rede pública de saúde.

⚠️ Para cadastrar ou acompanhar sua regulação, acesse o Bot Principal:
👉 {LINK_PRINCIPAL}

📋 Escolha uma opção abaixo:""", parse_mode="Markdown", reply_markup=menu, disable_web_page_preview=True)

# ==================== /AJUDA ====================
@bot.message_handler(commands=['ajuda'])
def ajuda(msg):
    bot.send_message(msg.chat.id,
f"""❓ *Dúvidas Frequentes*

⏱️ *Prazos:* A verificação na FMS é feita periodicamente. Você será avisado(a) na atualização.
🔢 *Cartão SUS:* 15 dígitos, sem pontos nem traços.
📱 *Celular:* Com DDD, apenas números. Ex: 86999998888
📅 *Nascimento:* DD/MM/AAAA. Ex: 31/12/1990
🔤 *CBO:* Se não souber, digite 0.

🔑 *Problemas:* Use /suporte informando nome e Cartão SUS.

👉 Cadastro e acompanhamento no Bot Principal:
{LINK_PRINCIPAL}""", parse_mode="Markdown", disable_web_page_preview=True)

# ==================== /CADASTRAR ====================
@bot.message_handler(commands=['cadastrar'])
def cadastrar(msg):
    bot.send_message(msg.chat.id,
f"""📋 *Como Cadastrar sua Regulação*

O cadastro é feito no Bot Principal com estes dados:

1️⃣ Cartão SUS — 15 dígitos
2️⃣ Nome completo
3️⃣ Celular com DDD
4️⃣ Data de nascimento (DD/MM/AAAA)
5️⃣ CBO — digite 0 se não souber
6️⃣ Procedimento solicitado

👉 Cadastre aqui:
{LINK_PRINCIPAL}""", parse_mode="Markdown", disable_web_page_preview=True)

# ==================== /GERENCIAR ====================
@bot.message_handler(commands=['gerenciar'])
def gerenciar(msg):
    bot.send_message(msg.chat.id,
f"""🛠️ *Gerenciar Suas Regulações*

No Bot Principal você pode:

✅ Visualizar status
✏️ Corrigir dados
🗑️ Excluir regulações

👉 Acesse:
{LINK_PRINCIPAL}""", parse_mode="Markdown", disable_web_page_preview=True)

# ==================== /PLANOS ====================
@bot.message_handler(commands=['planos'])
def planos(msg):
    bot.send_message(msg.chat.id,
f"""💎 *Planos AlertaSUS 2.5*

Escolha o plano que melhor se adapta ao seu acompanhamento:

✅ Semestral — Apenas R$ 9,90
✅ Anual — Apenas R$ 14,99

Benefícios inclusos:
✅ Acompanhamento ilimitado de regulações
✅ Notificações em tempo real
✅ Suporte prioritário

👉 Para assinar e pagar, acesse o Bot Principal:
{LINK_PRINCIPAL}""", parse_mode="Markdown", disable_web_page_preview=True)

# ==================== /SOBRE ====================
@bot.message_handler(commands=['sobre'])
def sobre(msg):
    bot.send_message(msg.chat.id,
f"""ℹ️ *Sobre o AlertaSUS 2.5*

Sistema independente de acompanhamento de regulações de exames e consultas na rede pública de saúde.

⚠️ Não somos a FMS nem o SUS — apenas acompanhamos dados públicos disponíveis.

👉 Cadastre e acompanhe no Bot Principal:
{LINK_PRINCIPAL}""", parse_mode="Markdown", disable_web_page_preview=True)

# ==================== /SUPORTE ====================
@bot.message_handler(commands=['suporte'])
def suporte(msg):
    em_atendimento[msg.from_user.id] = True
    bot.send_message(msg.chat.id,
"""📞 *Atendimento*

✍️ Envie abaixo sua mensagem, dúvida ou problema.
Informe sempre seu nome completo e número do Cartão SUS.
Nossa equipe retornará em breve!""", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.from_user.id in em_atendimento)
def recebe_msg(msg):
    uid = msg.from_user.id
    texto = msg.text.strip()
    del em_atendimento[uid]
    supabase.table("chamados").insert({"usuario_id": uid, "mensagem_texto": texto}).execute()
    bot.send_message(msg.chat.id, "✅ Sua mensagem foi enviada! Responderemos em breve. Consulte /ajuda enquanto aguarda.")

# ==================== INICIAR ====================
if __name__ == "__main__":
    print("🤖 Central de Atendimento rodando...")
    try: bot.get_updates(offset=-1, timeout=0)
    except: pass
    bot.infinity_polling(timeout=12, long_polling_timeout=6)