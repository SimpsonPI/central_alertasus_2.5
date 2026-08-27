import telebot
from telebot import types
from supabase import create_client, Client
import mercadopago
from config import (
    BOT_PUBLICO_TOKEN, SUPABASE_URL, SUPABASE_KEY, MERCADO_PAGO_ACCESS_TOKEN, BOT_PRINCIPAL_LINK
)

bot = telebot.TeleBot(BOT_PUBLICO_TOKEN)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
mp = mercadopago.SDK(MERCADO_PAGO_ACCESS_TOKEN)

estado_suporte = {}

# ==================== COMANDO /START ====================
@bot.message_handler(commands=['start'])
def inicio(msg):
    uid = msg.from_user.id
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("/ajuda", "/suporte")
    markup.row("/planos", "/cadastrar")
    markup.row("/gerenciar", "/sobre")

    bot.send_message(msg.chat.id,
f"""🙋‍♂️ Bem-vindo(a) à *Central de Atendimento AlertaSUS 2.5*!

Seu ID único: `{uid}`

Aqui você encontra orientações, dúvidas frequentes e suporte para o sistema de acompanhamento de regulações.

⚠️ Para cadastrar ou acompanhar sua regulação, acesse o Bot Principal:
👉 [Clique aqui → Acessar Bot Principal]({BOT_PRINCIPAL_LINK})

📋 Escolha uma opção abaixo:""", parse_mode="Markdown", reply_markup=markup, disable_web_page_preview=True)

# ==================== COMANDO /AJUDA ====================
@bot.message_handler(commands=['ajuda'])
def ajuda(msg):
    bot.send_message(msg.chat.id,
"""❓ *Dúvidas Frequentes*

⏱️ *Prazos:* A FMS verifica periodicamente; você recebe aviso na atualização.

🔢 *Cartão SUS:* 15 dígitos, sem pontos/traços. Confira se está correto.

📱 *Celular:* Apenas números com DDD. Ex: 86999998888

📅 *Nascimento:* DD/MM/AAAA. Ex: 31/12/1990

🔤 *CBO:* Se não souber, digite 0.

📋 *Procedimento:* Nome ou código do exame/consulta.

🔑 *Problemas:* Use /suporte informando nome e Cartão SUS.

👉 Cadastro e acompanhamento no Bot Principal:
[Acessar →]({BOT_PRINCIPAL_LINK})""", parse_mode="Markdown", disable_web_page_preview=True)

# ==================== COMANDO /CADASTRAR ====================
@bot.message_handler(commands=['cadastrar'])
def cadastrar(msg):
    bot.send_message(msg.chat.id,
"""📋 *Como Cadastrar sua Regulação*

O cadastro é feito no Bot Principal com estes dados:

1️⃣ Cartão SUS — 15 dígitos
2️⃣ Nome completo
3️⃣ Celular com DDD
4️⃣ Data de nascimento (DD/MM/AAAA)
5️⃣ CBO — digite 0 se não souber
6️⃣ Procedimento solicitado

👉 [Clique aqui para cadastrar →]({BOT_PRINCIPAL_LINK})""", parse_mode="Markdown", disable_web_page_preview=True)

# ==================== COMANDO /GERENCIAR ====================
@bot.message_handler(commands=['gerenciar'])
def gerenciar(msg):
    bot.send_message(msg.chat.id,
"""🛠️ *Gerenciar Suas Regulações*

No Bot Principal você pode:

✅ Visualizar status
✏️ Corrigir dados
🗑️ Excluir regulações

👉 [Clique aqui para gerenciar →]({BOT_PRINCIPAL_LINK})""", parse_mode="Markdown", disable_web_page_preview=True)

# ==================== COMANDO /PLANOS ====================
@bot.message_handler(commands=['planos'])
def planos(msg):
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("Semestral — R$ 9,90", callback_data="plano_semestral"),
        types.InlineKeyboardButton("Anual — R$ 14,99", callback_data="plano_anual")
    )
    bot.send_message(msg.chat.id,
"""💎 *Planos AlertaSUS 2.5*

✅ Acompanhamento ilimitado
✅ Notificações em tempo real
✅ Suporte prioritário

Escolha abaixo:""", parse_mode="Markdown", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith("plano_"))
def gerar_pagamento(call):
    planos = {
        "plano_semestral": {"titulo": "Plano Semestral", "valor": 9.90},
        "plano_anual": {"titulo": "Plano Anual", "valor": 14.99}
    }
    escolha = planos.get(call.data)
    if not escolha:
        bot.answer_callback_query(call.id, "Plano inválido")
        return

    pref = {
        "items": [{"title": escolha["titulo"], "quantity": 1, "unit_price": escolha["valor"]}],
        "external_reference": f"usr_{call.from_user.id}",
        "payment_methods": {"excluded_payment_types": [{"id": "credit_card"}], "installments": 1}
    }
    resultado = mp.preference().create(pref)
    link = resultado["response"]["init_point"]

    bot.edit_message_text(
f"""💎 {escolha['titulo']}
Valor: R$ {escolha['valor']:.2f}

✅ Pague via Pix:""", call.message.chat.id, call.message.id,
        parse_mode="Markdown", reply_markup=types.InlineKeyboardMarkup([[types.InlineKeyboardButton("🔗 Pagar", url=link)]]))

# ==================== COMANDO /SOBRE ====================
@bot.message_handler(commands=['sobre'])
def sobre(msg):
    bot.send_message(msg.chat.id,
"""ℹ️ *Sobre o AlertaSUS 2.5*

Sistema independente de acompanhamento de regulações.
⚠️ Não somos a FMS/SUS — apenas acompanhamos dados públicos.

👉 Cadastre no Bot Principal:
[Acessar →]({BOT_PRINCIPAL_LINK})""", parse_mode="Markdown", disable_web_page_preview=True)

# ==================== COMANDO /SUPORTE ====================
@bot.message_handler(commands=['suporte'])
def suporte(msg):
    uid = msg.from_user.id
    estado_suporte[uid] = True
    bot.send_message(msg.chat.id,
"""📞 *Atendimento*

✍️ Envie sua mensagem abaixo com nome e Cartão SUS.
Retornaremos em breve!

👉 Cadastro e acompanhamento:
[Acessar Bot Principal →]({BOT_PRINCIPAL_LINK})""", parse_mode="Markdown", disable_web_page_preview=True)

@bot.message_handler(func=lambda m: m.from_user.id in estado_suporte)
def salvar_suporte(msg):
    uid = msg.from_user.id
    texto = msg.text.strip()
    del estado_suporte[uid]
    supabase.table("chamados").insert({"usuario_id": uid, "mensagem_texto": texto}).execute()
    bot.send_message(msg.chat.id, "✅ Enviado! Responderemos em breve. Consulte /ajuda enquanto aguarda.")

if __name__ == "__main__":
    print("🤖 Central de Atendimento rodando...")
    try: bot.get_updates(offset=-1, timeout=0)
    except: pass
    bot.infinity_polling(timeout=10, long_polling_timeout=5)