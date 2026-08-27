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

Aqui você encontra orientações, dúvidas frequentes e suporte para o sistema de acompanhamento de regulações de exames e consultas na rede pública de saúde.

⚠️ Para cadastrar ou acompanhar sua regulação, acesse o Bot Principal:
👉 [Clique aqui → Acessar Bot Principal AlertaSUS 2.5]({BOT_PRINCIPAL_LINK})

📋 Escolha uma opção abaixo:""", parse_mode="Markdown", reply_markup=markup, disable_web_page_preview=True)

# ==================== COMANDO /AJUDA ====================
@bot.message_handler(commands=['ajuda'])
def ajuda(msg):
    bot.send_message(msg.chat.id,
"""❓ *Dúvidas Frequentes — AlertaSUS 2.5*

⏱️ *Prazos de acompanhamento:*
A verificação na FMS é realizada periodicamente. Você será avisado(a) automaticamente assim que houver qualquer atualização no status da sua regulação.

🔢 *Cartão SUS:*
Deve conter exatamente 15 dígitos, sem pontos nem traços. É o número presente no seu cartão do SUS. Se estiver correto e mesmo assim não funcionar, confira se há espaços ou digitos a mais.

📱 *Celular com DDD:*
Digite apenas números, com DDD. Exemplo: `86999998888`

📅 *Data de nascimento:*
Use o formato **DD/MM/AAAA**. Exemplo: `31/12/1990`

🔤 *CBO:*
É o código da Classificação Brasileira de Ocupações. Se não souber, digite `0`.

📋 *Procedimento solicitado:*
Digite o nome ou código do exame, consulta ou procedimento que você está aguardando.

🔑 *Não consigo acessar minha regulação:*
Confirme que todos os dados foram digitados corretamente. Se persistir, envie mensagem via /suporte informando seu nome e Cartão SUS para verificarmos.

👉 Para cadastrar ou consultar, acesse:
[Bot Principal AlertaSUS 2.5]({BOT_PRINCIPAL_LINK})""", parse_mode="Markdown", disable_web_page_preview=True)

# ==================== COMANDO /CADASTRAR ====================
@bot.message_handler(commands=['cadastrar'])
def cadastrar(msg):
    bot.send_message(msg.chat.id,
"""📋 *Como Cadastrar sua Regulação*

O cadastro é feito **exclusivamente pelo Bot Principal AlertaSUS 2.5**. Você precisará informar:

1️⃣ *Cartão SUS* — 15 dígitos (apenas números)
2️⃣ *Nome completo* — seu nome completo
3️⃣ *Celular com DDD* — ex: 86999998888
4️⃣ *Data de nascimento* — formato DD/MM/AAAA
5️⃣ *CBO* — digite 0 se não souber
6️⃣ *Procedimento solicitado* — nome ou código do exame/consulta

✅ Após cadastrar, o sistema inicia automaticamente o acompanhamento e avisará você assim que houver atualização.

👉 [Clique aqui para cadastrar →]({BOT_PRINCIPAL_LINK})""", parse_mode="Markdown", disable_web_page_preview=True)

# ==================== COMANDO /GERENCIAR ====================
@bot.message_handler(commands=['gerenciar'])
def gerenciar(msg):
    bot.send_message(msg.chat.id,
"""🛠️ *Gerenciar Suas Regulações*

No Bot Principal AlertaSUS 2.5 você pode:

✅ *Visualizar* — conferir o status atual de todas as suas regulações
✏️ *Corrigir dados* — alterar nome, celular, CBO ou procedimento
🗑️ *Excluir* — remover regulações antigas ou cadastradas por engano

⚠️ Para segurança, só é possível alterar/excluir a partir do ID informado no próprio Bot Principal.

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
"""💎 *Conheça os Planos AlertaSUS 2.5*

Escolha o período que melhor se adapta ao seu acompanhamento:

✅ Acompanhamento ilimitado de regulações
✅ Notificações em tempo real
✅ Suporte prioritário
✅ Atualizações automáticas de status

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

✅ Pagamento via Pix — liberado em até 2 horas após confirmação.

🔒 Pagamento seguro pelo Mercado Pago.
👉 Clique abaixo para concluir:""",
        call.message.chat.id, call.message.id, parse_mode="Markdown",
        reply_markup=types.InlineKeyboardMarkup(
            [[types.InlineKeyboardButton("🔗 Pagar via Pix", url=link_pagamento)]]
        )
    )

# ==================== COMANDO /SOBRE ====================
@bot.message_handler(commands=['sobre'])
def sobre(msg):
    bot.send_message(msg.chat.id,
"""ℹ️ *Sobre o AlertaSUS 2.5*

O AlertaSUS é um sistema independente de acompanhamento de regulações de exames e consultas na rede pública de saúde.

✅ O que faz:
- Monitora periodicamente o andamento da sua regulação na FMS
- Avisa você automaticamente quando houver alteração de status
- Centraliza todas as suas regulações em um só lugar

⚠️ Importante:
- Não realizamos agendamento nem temos vínculo oficial com a FMS ou SUS
- Apenas acompanhamos a informação pública disponível
- O prazo e a aprovação dependem exclusivamente da unidade de saúde

👉 Cadastre e acompanhe no Bot Principal:
[Clique aqui → AlertaSUS 2.5]({BOT_PRINCIPAL_LINK})""", parse_mode="Markdown", disable_web_page_preview=True)

# ==================== COMANDO /SUPORTE ====================
@bot.message_handler(commands=['suporte'])
def suporte(msg):
    uid = msg.from_user.id
    estado_suporte[uid] = True
    bot.send_message(msg.chat.id,
"""📞 *Atendimento — AlertaSUS 2.5*

✍️ Envie abaixo sua mensagem, dúvida ou problema.
Informe sempre:
- Seu nome completo
- Número do Cartão SUS
- Detalhe da dúvida ou dificuldade

Nossa equipe retornará em breve!

⚠️ Para cadastro e acompanhamento, acesse:
[Bot Principal AlertaSUS 2.5]({BOT_PRINCIPAL_LINK})""", parse_mode="Markdown", disable_web_page_preview=True)

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

    bot.send_message(msg.chat.id,
"""✅ Sua mensagem foi enviada!

Nossa equipe analisará seu atendimento e responderá o mais breve possível.

⚠️ Dica: consulte sempre /ajuda antes — sua dúvida pode estar respondida lá!""")

if __name__ == "__main__":
    print("🤖 Central de Atendimento AlertaSUS 2.5 rodando...")
    try:
        bot.get_updates(offset=-1, timeout=0)
    except:
        pass
    bot.infinity_polling(timeout=10, long_polling_timeout=5)