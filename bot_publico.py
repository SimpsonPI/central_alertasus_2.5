import telebot
from telebot import types
from supabase import create_client, Client
import mercadopago
import os
from dotenv import load_dotenv

load_dotenv()

# ====== LEITURA DAS VARIÁVEIS DO AMBIENTE ======
BOT_TOKEN = os.getenv("BOT_PUBLICO_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
MP_TOKEN = os.getenv("MERCADO_PAGO_ACCESS_TOKEN")
LINK_PRINCIPAL = os.getenv("BOT_PRINCIPAL_LINK", "https://t.me/SEU_BOT")

bot = telebot.TeleBot(BOT_TOKEN)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
mp = mercadopago.SDK(MP_TOKEN)

em_atendimento = {}

# ====== /START ======
@bot.message_handler(commands=['start'])
def inicio(msg):
    uid = msg.from_user.id
    menu = types.ReplyKeyboardMarkup(resize_keyboard=True)
    menu.row("/ajuda", "/suporte")
    menu.row("/planos", "/cadastrar")
    menu.row("/gerenciar", "/sobre")

    bot.send_message(msg.chat.id,
f"""🙋‍♂️ *Central de Atendimento AlertaSUS 2.5*

Seu ID: `{uid}`

Aqui você encontra ajuda e orientações sobre o sistema.

⚠️ Para cadastrar ou acompanhar, use o Bot Principal:
👉 {LINK_PRINCIPAL}

Escolha uma opção:""", parse_mode="Markdown", reply_markup=menu, disable_web_page_preview=True)

# ====== /AJUDA ======
@bot.message_handler(commands=['ajuda'])
def ajuda(msg):
    bot.send_message(msg.chat.id,
f"""❓ *Dúvidas Frequentes*

⏱️ Acompanhamento: atualizado periodicamente.
🔢 Cartão SUS: 15 dígitos, sem pontos.
📱 Celular: com DDD, só números.
📅 Nascimento: DD/MM/AAAA.
🔤 CBO: digite 0 se não souber.

👉 Cadastro e mais ajuda no Bot Principal:
{LINK_PRINCIPAL}""", parse_mode="Markdown", disable_web_page_preview=True)

# ====== /CADASTRAR ======
@bot.message_handler(commands=['cadastrar'])
def cadastrar(msg):
    bot.send_message(msg.chat.id,
f"""📋 *Como Cadastrar*

O cadastro é feito no Bot Principal com:
1️⃣ Cartão SUS (15 dígitos)
2️⃣ Nome completo
3️⃣ Celular com DDD
4️⃣ Data de nascimento
5️⃣ CBO → 0 se não souber
6️⃣ Procedimento

👉 Cadastre aqui:
{LINK_PRINCIPAL}""", parse_mode="Markdown", disable_web_page_preview=True)

# ====== /GERENCIAR ======
@bot.message_handler(commands=['gerenciar'])
def gerenciar(msg):
    bot.send_message(msg.chat.id,
f"""🛠️ *Gerenciar Regulações*

No Bot Principal você pode:
✅ Ver status
✏️ Corrigir dados
🗑️ Excluir

👉 Acesse:
{LINK_PRINCIPAL}""", parse_mode="Markdown", disable_web_page_preview=True)

# ====== /PLANOS ======
@bot.message_handler(commands=['planos'])
def planos(msg):
    botoes = types.InlineKeyboardMarkup()
    botoes.add(
        types.InlineKeyboardButton("Semestral — R$ 9,90", callback_data="plano_sem"),
        types.InlineKeyboardButton("Anual — R$ 14,99", callback_data="plano_ano")
    )
    bot.send_message(msg.chat.id,
"""💎 *Planos AlertaSUS 2.5*

✅ Acompanhamento ilimitado
✅ Avisos na hora
✅ Suporte prioritário

Escolha:""", reply_markup=botoes, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda c: c.data.startswith("plano_"))
def pagamentos(call):
    dados = {
        "plano_sem": {"nome": "Semestral", "valor": 9.90},
        "plano_ano": {"nome": "Anual", "valor": 14.99}
    }
    esc = dados.get(call.data)
    if not esc:
        bot.answer_callback_query(call.id, "Inválido")
        return

    req = {
        "items": [{"title": f"Plano {esc['nome']}", "quantity":1, "unit_price": esc["valor"]}],
        "external_reference": f"usr_{call.from_user.id}",
        "payment_methods": {"excluded_payment_types":[{"id":"credit_card"}], "installments":1}
    }
    link = mp.preference().create(req)["response"]["init_point"]

    bot.edit_message_text(
f"""💎 Plano {esc['nome']}
Valor: R$ {esc['valor']:.2f}

✅ Pague via Pix:""", call.message.chat.id, call.message.id, parse_mode="Markdown",
        reply_markup=types.InlineKeyboardMarkup([[types.InlineKeyboardButton("🔗 Pagar", url=link)]]))

# ====== /SOBRE ======
@bot.message_handler(commands=['sobre'])
def sobre(msg):
    bot.send_message(msg.chat.id,
f"""ℹ️ *Sobre o AlertaSUS 2.5*

Sistema independente de acompanhamento de regulações.
⚠️ Não somos a FMS/SUS — apenas acompanhamos dados públicos.

👉 Acesse o Bot Principal:
{LINK_PRINCIPAL}""", parse_mode="Markdown", disable_web_page_preview=True)

# ====== /SUPORTE ======
@bot.message_handler(commands=['suporte'])
def suporte(msg):
    em_atendimento[msg.from_user.id] = True
    bot.send_message(msg.chat.id,
"""📞 *Atendimento*

✍️ Escreva abaixo sua dúvida.
Informe nome e Cartão SUS. Responderemos em breve!""", parse_mode="Markdown")

@bot.message_handler(func=lambda m: m.from_user.id in em_atendimento)
def recebe_msg(msg):
    uid = msg.from_user.id
    texto = msg.text.strip()
    del em_atendimento[uid]
    supabase.table("chamados").insert({"usuario_id": uid, "mensagem_texto": texto}).execute()
    bot.send_message(msg.chat.id, "✅ Enviado! Responderemos em breve. Consulte /ajuda enquanto aguarda.")

# ====== INICIAR ======
if __name__ == "__main__":
    print("🤖 Central de Atendimento rodando...")
    try: bot.get_updates(offset=-1, timeout=0)
    except: pass
    bot.infinity_polling(timeout=10, long_polling_timeout=5)