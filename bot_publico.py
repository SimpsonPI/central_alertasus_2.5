import telebot
from telebot import types
from supabase import create_client, Client
import mercadopago
from config import (
    BOT_PUBLICO_TOKEN, SUPABASE_URL, SUPABASE_KEY, MERCADO_PAGO_ACCESS_TOKEN
)

bot = telebot.TeleBot(BOT_PUBLICO_TOKEN)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
mp = mercadopago.SDK(MERCADO_PAGO_ACCESS_TOKEN)

estado_suporte = {}

# ==================== LINK DO BOT PRINCIPAL ALERTASUS 2.0 ====================
BOT_PRINCIPAL_LINK = "https://t.me/meu_atendimento_123_bot"  # ⚠️ Troque pelo link REAL do bot principal

# ==================== COMANDO /START ====================
@bot.message_handler(commands=['start'])
def inicio(msg):
    uid = msg.from_user.id
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("/ajuda", "/suporte")
    markup.row("/planos", "/cadastrar")
    markup.row("/gerenciar")

    bot.send_message(msg.chat.id,
f"""🙋‍♂️ Bem-vindo(a) à *Central de Atendimento AlertaSUS 2.0*!

Seu ID único: `{uid}`

Aqui você encontra orientações e suporte para o sistema de acompanhamento de regulações de exames e consultas na rede pública de saúde.

📋 Escolha uma opção abaixo:""",
        parse_mode="Markdown", reply_markup=markup
    )

# ==================== COMANDO /AJUDA ====================
@bot.message_handler(commands=['ajuda'])
def ajuda(msg):
    bot.send_message(msg.chat.id,
"""❓ *Dúvidas Frequentes — AlertaSUS 2.0*

⏱️ *Prazos de acompanhamento:* A verificação na FMS é realizada periodicamente; você será avisado(a) assim que houver atualização.

🔑 *Problemas de acesso:* Confirme que seu Cartão SUS foi digitado corretamente (15 dígitos).

📋 *Cadastro e acompanhamento:* Para cadastrar ou consultar suas regulações, acesse o bot principal do AlertaSUS 2.0 pelo link abaixo.

👉 [Acessar Bot Principal AlertaSUS 2.0](""" + BOT_PRINCIPAL_LINK + """)""", parse_mode="Markdown", disable_web_page_preview=True)

# ==================== COMANDO /SUPORTE ====================
@bot.message_handler(commands=['suporte'])
def suporte(msg):
    uid = msg.from_user.id
    estado_suporte[uid] = True
    bot.send_message(msg.chat.id,
"""📞 *Atendimento — AlertaSUS 2.0*

✍️ Envie abaixo sua mensagem, dúvida ou problema que nossa equipe retornará em breve!

👉 Para cadastrar ou gerenciar suas regulações, acesse:
[Acessar Bot Principal AlertaSUS 2.0](""" + BOT_PRINCIPAL_LINK + """)""", parse_mode="Markdown", disable_web_page_preview=True)

# ==================== COMANDO /PLANOS ====================
@bot.message_handler(commands=['planos'])
def planos(msg):
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("Semestral — R$ 9,90", callback_data="plano_semestral"),
        types.InlineKeyboardButton("Anual — R$ 14,99", callback_data="plano_anual")
    )
    bot.send_message(msg.chat.id,
"""💎 *Conheça os Planos AlertaSUS 2.0*

✅ Acompanhamento ilimitado de regulações
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

    preferencia = {
        "items": [{"title": escolha["titulo"], "quantity": 1, "unit_price": escolha["valor"]}],
        "external_reference": f"usr_{call.from_user.id}",
        "payment_methods": {"excluded_payment_types": [{"id": "credit_card"}], "installments": 1}
    }
    resultado = mp.preference().create(preferencia)
    link_pagamento = resultado["response"]["init_point"]

    bot.edit_message_text(
f"""💎 {escolha['titulo']}
Valor: R$ {escolha['valor']:.2f}

✅ Clique abaixo para pagar via Pix:""",
        call.message.chat.id, call.message.id, parse_mode="Markdown",
        reply_markup=types.InlineKeyboardMarkup(
            [[types.InlineKeyboardButton("🔗 Pagar via Pix", url=link_pagamento)]]
        )
    )

# ==================== COMANDO /CADASTRAR — Apenas Instruções + Link ====================
@bot.message_handler(commands=['cadastrar'])
def cadastrar(msg):
    bot.send_message(msg.chat.id,
"""📋 *Como Cadastrar sua Regulação*

Para cadastrar seu acompanhamento, você precisará informar:

1️⃣ Cartão SUS — 15 dígitos
2️⃣ Nome completo
3️⃣ Celular com DDD
4️⃣ Data de nascimento (DD/MM/AAAA)
5️⃣ CBO — Classificação Brasileira de Ocupações (digite 0 se não souber)
6️⃣ Procedimento solicitado

✅ O cadastro é feito exclusivamente pelo bot principal do AlertaSUS 2.0.

👉 [Clique aqui para cadastrar](""" + BOT_PRINCIPAL_LINK + """)""", parse_mode="Markdown", disable_web_page_preview=True)

# ==================== COMANDO /GERENCIAR — Apenas Instruções + Link ====================
@bot.message_handler(commands=['gerenciar'])
def gerenciar(msg):
    bot.send_message(msg.chat.id,
"""🛠️ *Gerenciar Suas Regulações*

Para visualizar, corrigir ou excluir suas regulações cadastradas, acesse o bot principal do AlertaSUS 2.0:

✅ Visualizar regulações
✏️ Corrigir dados cadastrados
🗑️ Excluir regulações

👉 [Clique aqui para gerenciar](""" + BOT_PRINCIPAL_LINK + """)""", parse_mode="Markdown", disable_web_page_preview=True)

# ==================== RECEBER MENSAGEM DE SUPORTE ====================
@bot.message_handler(func=lambda m: m.from_user.id in estado_suporte)
def salvar_suporte(msg):
    uid = msg.from_user.id
    texto = msg.text.strip()
    del estado_suporte[uid]

    supabase.table("chamados").insert({
        "usuario_id": uid,
        "mensagem_texto": texto
    }).execute()

    bot.send_message(msg.chat.id, "✅ Sua mensagem foi enviada! Em breve nossa equipe responderá.")

if __name__ == "__main__":
    print("🤖 Central de Atendimento AlertaSUS 2.0 rodando...")
    try:
        bot.get_updates(offset=-1, timeout=0)
    except:
        pass
    bot.infinity_polling(timeout=10, long_polling_timeout=5)