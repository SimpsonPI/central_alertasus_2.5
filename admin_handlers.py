import os
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from admin_central import (
    STATUS_EMOJI,
    obter_chamados_pendentes,
    formatar_lista_chamados,
    estatisticas_chamados,
    formatar_estatisticas,
)
from database_atendimento import responder_chamado, supabase

ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]

AGUARDANDO_RESPOSTA_ADMIN = 1


def eh_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

async def _editar(query, texto, reply_markup=None, parse_mode=None):
    """Edita a mensagem de um callback, ignorando o erro 'Message is not modified'."""
    try:
        await query.edit_message_text(
            texto,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
        )
    except Exception as e:
        # Erro inofensivo: nada mudou na mensagem
        if "Message is not modified" in str(e):
            return
        raise

def _teclado_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Todos pendentes", callback_data="adm_todos")],
        [InlineKeyboardButton("🟢 Abertos", callback_data="adm_aberto"),
         InlineKeyboardButton("🔵 Em andamento", callback_data="adm_em_atend")],
        [InlineKeyboardButton("📊 Estatísticas", callback_data="adm_stats")],
    ])


async def menu_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not eh_admin(update.effective_user.id):
        await update.message.reply_text("⛔ Acesso restrito.")
        return

    await update.message.reply_text(
        "🏛️ *Central Admin VigiaSaúde*\nEscolha uma opção:",
        reply_markup=_teclado_menu(),
        parse_mode="Markdown"
    )

async def _renderizar_lista_chamados(query, status_filtro=None):
    """Renderiza a lista de chamados pendentes (usada por callback_listar e callback_finalizar)."""
    chamados = await obter_chamados_pendentes(status_filtro=status_filtro)
    chamados.sort(key=lambda c: c.get("created_at") or "")

    if not chamados:
        await query.edit_message_text(
            "📭 Nenhum chamado pendente no momento.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Voltar", callback_data="adm_voltar")]
            ])
        )
        return

    titulo = "📋 *CHAMADOS PENDENTES*"
    if status_filtro == "aberto":
        titulo = "🟢 *CHAMADOS EM ABERTO*"
    elif status_filtro == "em_andamento":
        titulo = "🔵 *CHAMADOS EM ANDAMENTO*"

    texto = f"{titulo} ({len(chamados)})\n\nToque em um chamado para ver os detalhes."

    botoes = []
    for ch in chamados[:30]:
        emoji = STATUS_EMOJI.get(ch.get("status"), "❔")
        nome = ch.get("nome_usuario") or ch.get("chat_id") or "?"
        if len(nome) > 25:
            nome = nome[:22] + "…"
        label = f"{emoji} #{ch['id']} — {nome}"
        botoes.append([
            InlineKeyboardButton(label, callback_data=f"adm_ver_{ch['id']}")
        ])

    botoes.append([InlineKeyboardButton("🔙 Voltar", callback_data="adm_voltar")])

    await _editar(query, texto, reply_markup=..., parse_mode=...)

async def callback_listar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if not eh_admin(query.from_user.id):
        await query.edit_message_text("⛔ Acesso restrito.")
        return

    mapa = {
        "adm_todos": None,
        "adm_aberto": "aberto",
        "adm_em_atend": "em_andamento",
    }
    status_filtro = mapa.get(query.data)

    await _renderizar_lista_chamados(query, status_filtro=status_filtro)

async def callback_estatisticas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if not eh_admin(query.from_user.id):
        return

    stats = await estatisticas_chamados()
    texto = formatar_estatisticas(stats)
    await query.edit_message_text(
        texto,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Voltar", callback_data="adm_voltar")]
        ]),
        parse_mode="Markdown"
    )


async def callback_voltar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🏛️ *Central Admin VigiaSaúde*\nEscolha uma opção:",
        reply_markup=_teclado_menu(),
        parse_mode="Markdown"
    )


async def callback_ver_chamado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exibe detalhes de um chamado específico."""
    query = update.callback_query
    await query.answer()
    if not eh_admin(query.from_user.id):
        return

    chamado_id = int(query.data.replace("adm_ver_", ""))

    botoes_voltar = [
        [InlineKeyboardButton("🔙 Voltar", callback_data="adm_voltar")]
    ]

    chamados = await obter_chamados_pendentes()
    chamado = next((c for c in chamados if c["id"] == chamado_id), None)

    if not chamado:
        await query.edit_message_text(
            f"❌ Chamado #{chamado_id} não encontrado ou já finalizado.",
            reply_markup=InlineKeyboardMarkup(botoes_voltar),
        )
        return

    nome = chamado.get("nome_usuario") or chamado.get("chat_id") or "?"
    msg_usuario = (chamado.get("mensagem") or "(sem mensagem)").strip()

    texto = (
        f"📌 CHAMADO #{chamado['id']}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👤 {nome}\n"
        f"🆔 {chamado.get('chat_id')}\n"
        f"🏷️ {chamado.get('status')}\n"
        f"⚡ {chamado.get('prioridade')}\n"
        f"🕐 {chamado.get('created_at')}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💬 *Mensagem do usuário:*\n\n"
        f"_{msg_usuario}_"
    )

    if chamado.get("resposta_admin"):
        texto += (
            f"\n\n━━━━━━━━━━━━━━━━━━━\n"
            f"✅ *Sua resposta:*\n\n"
            f"_{chamado['resposta_admin']}_"
        )

    botoes = [
        [InlineKeyboardButton("✍️ Responder", callback_data=f"adm_responder_{chamado_id}")],
        [InlineKeyboardButton("✅ Finalizar", callback_data=f"adm_finalizar_{chamado_id}")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="adm_voltar")],
    ]

    await query.edit_message_text(
        texto,
        reply_markup=InlineKeyboardMarkup(botoes),
        parse_mode="Markdown"
    )

def _buscar_chamado_por_id(chamado_id: int) -> dict | None:
    res = supabase.table("chamados_suporte").select("*").eq("id", chamado_id).execute()
    return res.data[0] if res.data else None


async def callback_responder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print(">>> callback_responder CHAMADO")   # ← adicione essa linha
    query = update.callback_query
    await query.answer()
    if not eh_admin(query.from_user.id):
        return ConversationHandler.END

    chamado_id = int(query.data.replace("adm_responder_", ""))
    context.user_data["respondendo_chamado"] = chamado_id

    await query.edit_message_text(
        f"✍️ Responder chamado #{chamado_id}\n\n"
        "Digite a resposta que será enviada ao usuário.\n\n"
        "Ou toque em Cancelar.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancelar", callback_data=f"adm_cancelar_resp_{chamado_id}")]
        ])
    )
    return AGUARDANDO_RESPOSTA_ADMIN

async def callback_cancelar_resposta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.pop("respondendo_chamado", None)

    chamado_id = int(query.data.replace("adm_cancelar_resp_", ""))

    # Volta direto para a tela do chamado (sem simular query.data)
    botoes_voltar = [
        [InlineKeyboardButton("🔙 Voltar", callback_data="adm_voltar")]
    ]
    chamados = await obter_chamados_pendentes()
    chamado = next((c for c in chamados if c["id"] == chamado_id), None)

    if not chamado:
        await query.edit_message_text(
            f"❌ Chamado #{chamado_id} não encontrado.",
            reply_markup=InlineKeyboardMarkup(botoes_voltar),
        )
        return ConversationHandler.END

    nome = chamado.get("nome_usuario") or chamado.get("chat_id") or "?"
    msg_usuario = (chamado.get("mensagem") or "(sem mensagem)").strip()

    texto = (
        f"📌 CHAMADO #{chamado['id']}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👤 {nome}\n"
        f"🆔 {chamado.get('chat_id')}\n"
        f"🏷️ {chamado.get('status')}\n"
        f"⚡ {chamado.get('prioridade')}\n"
        f"🕐 {chamado.get('created_at')}\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"💬 Mensagem do usuário:\n\n{msg_usuario}"
    )

    if chamado.get("resposta_admin"):
        texto += f"\n\n✅ Sua resposta:\n{chamado['resposta_admin']}"

    botoes = [
        [InlineKeyboardButton("✍️ Responder", callback_data=f"adm_responder_{chamado_id}")],
        [InlineKeyboardButton("✅ Finalizar", callback_data=f"adm_finalizar_{chamado_id}")],
        [InlineKeyboardButton("🔙 Voltar", callback_data="adm_voltar")],
    ]

    await query.edit_message_text(
        texto,
        reply_markup=InlineKeyboardMarkup(botoes),
    )
    return ConversationHandler.END

async def receber_resposta_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recebe o texto do admin, salva, tenta enviar e volta pra tela do chamado."""
    if not eh_admin(update.effective_user.id):
        return ConversationHandler.END

    chamado_id = context.user_data.get("respondendo_chamado")
    texto = update.message.text
    context.user_data.pop("respondendo_chamado", None)

    chamado = _buscar_chamado_por_id(chamado_id)
    if not chamado:
        await update.message.reply_text("❌ Chamado não encontrado.")
        return ConversationHandler.END

    # Salva no banco
    await responder_chamado(chamado_id, texto, str(update.effective_user.id))

    # Tenta enviar ao usuário
    aviso = "✅ Resposta enviada ao usuário."
    try:
        await context.bot.send_message(
            chat_id=chamado["chat_id"],
            text=(
                f"📩 Resposta do suporte (chamado #{chamado_id}):\n\n"
                f"{texto}"
            ),
        )
    except Exception as e:
        err = str(e).lower()
        if "chat not found" in err or "bot was blocked" in err:
            aviso = (
                "⚠️ Resposta *salva no banco*, mas o usuário ainda não "
                "iniciou conversa com o bot — não foi possível notificá-lo."
            )
        else:
            aviso = f"⚠️ Resposta salva, mas houve erro no envio:\n`{e}`"

    # Recarrega o chamado com os dados atualizados
    chamado = _buscar_chamado_por_id(chamado_id)

    texto_view = (
        f"{aviso}\n\n"
        f"📌 CHAMADO #{chamado['id']}\n\n"
        f"👤 Usuário: {chamado.get('nome_usuario') or chamado.get('chat_id')}\n"
        f"🆔 Chat ID: {chamado.get('chat_id')}\n"
        f"🏷️ Status: {chamado.get('status')}\n"
        f"💬 Mensagem original:\n{chamado.get('mensagem')}\n\n"
        f"✅ Sua resposta:\n{texto}"
    )

    botoes = [
        [InlineKeyboardButton("✅ Finalizar", callback_data=f"adm_finalizar_{chamado_id}")],
        [InlineKeyboardButton("🔙 Voltar ao menu", callback_data="adm_voltar")],
    ]

    await update.message.reply_text(
        texto_view,
        reply_markup=InlineKeyboardMarkup(botoes),
    )

    return ConversationHandler.END


async def cancelar_resposta_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop("respondendo_chamado", None)
    await update.message.reply_text("❌ Resposta cancelada.")
    return ConversationHandler.END


async def callback_finalizar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin clicou em 'Finalizar' — marca o chamado como fechado."""
    query = update.callback_query
    await query.answer()
    if not eh_admin(query.from_user.id):
        return

    chamado_id = int(query.data.replace("adm_finalizar_", ""))
    chamado = _buscar_chamado_por_id(chamado_id)

    if not chamado:
        await query.edit_message_text("❌ Chamado não encontrado.")
        return

    # Atualiza e VERIFICA se funcionou
    try:
        res = supabase.table("chamados_suporte").update({
            "status": "fechado"
        }).eq("id", chamado_id).execute()
    except Exception as e:
        await query.edit_message_text(
            f"❌ Erro ao finalizar chamado #{chamado_id}:\n{e}"
        )
        return

    if not res.data:
        await query.edit_message_text(
            f"⚠️ O banco NÃO atualizou o chamado #{chamado_id}.\n\n"
            f"Isso normalmente significa que a coluna 'status' não aceita "
            f"o valor 'fechado'.\n\n"
            f"Verifique no Supabase se o enum da coluna status inclui 'fechado'. "
            f"Se não, adicione (ou troque o valor aqui para um existente, "
            f"como 'resolvido')."
        )
        return

    chamado = res.data[0]

    # Avisa o usuário (não bloqueia se falhar)
    try:
        await context.bot.send_message(
            chat_id=chamado["chat_id"],
            text=(
                f"✅ Seu chamado #{chamado_id} foi finalizado.\n"
                "Obrigado pelo contato! Se precisar, é só chamar de novo."
            ),
        )
    except Exception:
        pass

        # Volta automaticamente para a lista atualizada
    await _renderizar_lista_chamados(query, status_filtro=None)