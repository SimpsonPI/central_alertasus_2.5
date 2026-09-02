# handler_atendimento.py
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from ia_atendimento import gerar_resposta_ia

from database_atendimento import (
    buscar_faq_por_palavras_chave,
    registrar_chamado_suporte,
    adicionar_mensagem_fila,
    registrar_historico,
    obter_email_suporte,
    buscar_contexto_usuario,  # <-- Corrigido
)
from database import supabase

try:
    from config import ADMIN_CHAT_ID
    ADMIN_ID = ADMIN_CHAT_ID or 5242040324
except ImportError:
    ADMIN_ID = 5242040324

logger = logging.getLogger(__name__)

# Estados da conversa
AGUARDANDO_MENSAGEM_CHAMADO = 1

# ==========================================
# MENU DE ATENDIMENTO
# ==========================================

async def menu_atendimento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Boas-vindas - já inicia a interação por texto com a IA."""
    if update.callback_query:
        await update.callback_query.answer()
    
    texto = (
        "👋 Olá! Sou o assistente virtual do **VigiaSaude**.\n\n"
        "Pode digitar sua dúvida abaixo que responderei imediatamente. 😊\n\n"
        "Exemplos:\n"
        "• Como cadastrar uma regulação?\n"
        "• Como verificar o status?\n"
        "• Quanto custa o plano trimestral?\n"
    )
    
    # Envia apenas a mensagem, sem botões (para o usuário já digitar)
    if update.message:
        await update.message.reply_text(texto, parse_mode="Markdown")
    elif update.callback_query:
        await update.callback_query.edit_message_text(texto, parse_mode="Markdown")

# ==========================================
# FAQ AUTOMATIZADO
# ==========================================

async def iniciar_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia o atendimento via FAQ automático."""
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        
        texto = (
            "📚 <b>FAQ Automático - VigiaSaude</b>\n\n"
            "Digite abaixo sua dúvida que nossa IA tentará responder automaticamente.\n"
            "Ou clique em um dos tópicos abaixo:\n\n"
            "1️⃣ Como cadastrar uma regulação?\n"
            "2️⃣ Como consultar minhas regulações?\n"
            "3️⃣ Onde encontrar o Cartão SUS ou ID?\n"
            "4️⃣ Como alterar meus dados?\n"
            "5️⃣ Planos e Assinaturas\n"
            "6️⃣ O VigiaSaude tem vínculo com o governo?"
        )
        
        teclado = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("1️⃣ Cadastrar", callback_data="faq_cadastrar"),
                InlineKeyboardButton("2️⃣ Consultar", callback_data="faq_consultar")
            ],
            [
                InlineKeyboardButton("3️⃣ Cartão SUS/ID", callback_data="faq_id"),
                InlineKeyboardButton("4️⃣ Alterar Dados", callback_data="faq_alterar")
            ],
            [
                InlineKeyboardButton("5️⃣ Planos", callback_data="faq_planos"),
                InlineKeyboardButton("6️⃣ Vínculo Governo", callback_data="faq_governo")
            ],
            [InlineKeyboardButton("👤 Falar com Humano", callback_data="atendimento_humanizado")],
            [InlineKeyboardButton("⬅️ Voltar", callback_data="atendimento_menu")]
        ])
        
        await query.edit_message_text(texto, parse_mode="HTML", reply_markup=teclado)
    else:
        texto = (
            "📚 <b>FAQ Automático - VigiaSaude</b>\n\n"
            "Digite abaixo sua dúvida que nossa IA tentará responder automaticamente.\n"
            "Ou clique em um dos tópicos abaixo:"
        )
        
        teclado = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("1️⃣ Cadastrar", callback_data="faq_cadastrar"),
                InlineKeyboardButton("2️⃣ Consultar", callback_data="faq_consultar")
            ],
            [
                InlineKeyboardButton("3️⃣ Cartão SUS/ID", callback_data="faq_id"),
                InlineKeyboardButton("4️⃣ Alterar Dados", callback_data="faq_alterar")
            ],
            [
                InlineKeyboardButton("5️⃣ Planos", callback_data="faq_planos"),
                InlineKeyboardButton("6️⃣ Vínculo Governo", callback_data="faq_governo")
            ],
            [InlineKeyboardButton("👤 Falar com Humano", callback_data="atendimento_humanizado")],
            [InlineKeyboardButton("⬅️ Voltar", callback_data="atendimento_menu")]
        ])
        
        await update.message.reply_text(texto, parse_mode="HTML", reply_markup=teclado)
    
    context.user_data["modo_atendimento"] = "faq"


async def processar_pergunta_faq(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa a pergunta do usuário e tenta responder via FAQ ou IA (com contexto)."""
    if not update.message or not update.message.text:
        return

    # 🔓 REMOVIDO: verificação de modo_atendimento (agora funciona em qualquer mensagem)
    texto_usuario = update.message.text

    if texto_usuario.startswith("/"):
        return

    # 1. Busca contexto do usuário no Supabase
    chat_id = str(update.effective_user.id)
    contexto_usuario = await buscar_contexto_usuario(chat_id)

    # 2. Primeiro tenta encontrar resposta no FAQ estático
    resposta_faq = await buscar_faq_por_palavras_chave(texto_usuario)

    # 3. Se não encontrou no FAQ, tenta usar a IA com contexto
    if not resposta_faq:
        resposta_ia = await gerar_resposta_ia(
            texto_usuario,
            {
                "nome_usuario": update.effective_user.first_name,
                "chat_id": chat_id,
                "contexto_usuario": contexto_usuario  # <-- PASSA O CONTEXTO
            }
        )
        if resposta_ia:
            resposta_faq = {"resposta": resposta_ia}

    # 4. Se encontrou resposta (FAQ ou IA), envia
    if resposta_faq:
        await registrar_historico(
            chat_id=chat_id,
            tipo="faq_automatico",
            mensagem=texto_usuario,
            origem="bot"
        )

        await update.message.reply_text(
            resposta_faq["resposta"],
            parse_mode="HTML"
        )

        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton("👤 Falar com Atendente", callback_data="atendimento_humanizado")],
            [InlineKeyboardButton("❓ Outra pergunta", callback_data="atendimento_faq")]
        ])

        await update.message.reply_text(
            "Sua dúvida foi respondida? Se precisar de mais ajuda, fale com nossa equipe!",
            reply_markup=teclado
        )
    else:
        # 5. Se nem FAQ nem IA responderam, direciona para atendimento humanizado
        await update.message.reply_text(
            "🤔 Não encontrei uma resposta automática para sua pergunta.\n\n"
            "Vou direcionar você para nosso atendimento humanizado para que possamos ajudar melhor!"
        )

        await iniciar_atendimento_humanizado(update, context, mensagem_inicial=texto_usuario)
# ==========================================
# ATENDIMENTO HUMANIZADO
# ==========================================

async def iniciar_atendimento_humanizado(update: Update, context: ContextTypes.DEFAULT_TYPE, mensagem_inicial: str = None):
    """Inicia o atendimento humanizado."""
    
    if update.callback_query:
        query = update.callback_query
        await query.answer()
        
        texto = (
            "👤 <b>Atendimento Humanizado - VigiaSaude</b>\n\n"
            "Você será atendido por nossa equipe especializada.\n\n"
            "Por favor, descreva sua dúvida ou problema abaixo.\n"
            "Nossa equipe responderá o mais breve possível (horário comercial: 08h às 18h).\n\n"
            "<i>Digite sua mensagem agora:</i>"
        )
        
        await query.edit_message_text(texto, parse_mode="HTML")
    else:
        await update.message.reply_text(
            "👤 <b>Atendimento Humanizado - VigiaSaude</b>\n\n"
            "Por favor, descreva sua dúvida ou problema abaixo.\n"
            "Nossa equipe responderá o mais breve possível.\n\n"
            "<i>Digite sua mensagem agora:</i>",
            parse_mode="HTML"
        )
    
    context.user_data["modo_atendimento"] = "humanizado"
    
    if mensagem_inicial:
        await processar_mensagem_humanizado(update, context, mensagem_inicial)
    
    return AGUARDANDO_MENSAGEM_CHAMADO


async def processar_mensagem_humanizado(update: Update, context: ContextTypes.DEFAULT_TYPE, mensagem_texto: str = None):
    """Processa a mensagem do usuário no atendimento humanizado."""
    if context.user_data.get("modo_atendimento") != "humanizado":
        return

    mensagem = mensagem_texto or (update.message.text if update.message else None)
    if not mensagem:
        return

    user = update.effective_user
    chat_id = str(user.id)
    nome_usuario = f"{user.first_name} {user.last_name or ''}".strip() or "Usuário"

    chamado_id = await registrar_chamado_suporte(chat_id, nome_usuario, mensagem)

    if chamado_id:
        # Adiciona mensagem à fila
        await adicionar_mensagem_fila(chamado_id, chat_id, mensagem, "usuario")

        # Registra no histórico
        await registrar_historico(chat_id, "atendimento_humanizado", mensagem, "usuario")

        # Notifica o administrador
        try:
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    "🔔 <b>NOVO CHAMADO DE SUPORTE</b>\n\n"
                    f"📋 <b>Chamado ID:</b> <code>{chamado_id}</code>\n"
                    f"👤 <b>Usuário:</b> {nome_usuario}\n"
                    f"🆔 <b>Telegram ID:</b> <code>{chat_id}</code>\n"
                    f"📝 <b>Mensagem:</b>\n{mensagem}\n\n"
                    f"Use /responder <code>{chamado_id}</code> para responder."
                ),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Erro ao notificar admin: {e}")

        # Confirma ao usuário
        if update.message:
            await update.message.reply_text(
                "✅ <b>Mensagem recebida com sucesso!</b>\n\n"
                f"Seu protocolo de atendimento é: <code>#{chamado_id}</code>\n\n"
                "Nossa equipe analisará seu chamado e responderá em breve.\n"
                "Você receberá uma notificação assim que houver resposta.\n\n"
                "📧 Para contato direto, utilize nosso email: suporteVigiaSaude@gmail.com",
                parse_mode="HTML"
            )

        # Oferece opções
        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 Ver Meus Chamados", callback_data="ver_chamados")],
            [InlineKeyboardButton("⬅️ Voltar ao Menu", callback_data="iniciar")]
        ])

        if update.message:
            await update.message.reply_text(
                "O que deseja fazer agora?",
                reply_markup=teclado
            )
    else:
        # Se falhar ao registrar
        logger.error(f"FALHA ao registrar chamado para {chat_id} - mensagem: {mensagem}")
        if update.message:
            await update.message.reply_text(
                "❌ Ocorreu um erro ao registrar seu chamado.\n"
                "Por favor, tente novamente ou contate: suporteVigiaSaude@gmail.com"
            )

    return ConversationHandler.END

# ==========================================
# CANCELAR ATENDIMENTO
# ==========================================

async def cancelar_atendimento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela o atendimento humanizado."""
    
    context.user_data.pop("modo_atendimento", None)
    
    texto = "❌ Atendimento cancelado. Se precisar de algo, acesse o menu novamente!"
    
    if update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(texto)
    elif update.message:
        await update.message.reply_text(texto)
    
    return ConversationHandler.END


# ==========================================
# CALLBACK EMAIL DE SUPORTE
# ==========================================

async def callback_email_suporte(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exibe informações sobre email de suporte."""
    query = update.callback_query
    await query.answer()
    
    texto = (
        "📧 <b>Email de Suporte</b>\n\n"
        "Para entrar em contato com nossa equipe, utilize o email:\n\n"
        "<b>suporteVigiaSaude@gmail.com</b>\n\n"
        "Nossa equipe responderá o mais breve possível.\n\n"
        "<b>Horário de atendimento:</b>\n"
        "Segunda a Sexta: 08h às 18h\n"
        "Sábado: 08h às 12h"
    )
    
    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("⬅️ Voltar ao Menu de Atendimento", callback_data="atendimento_menu")],
        [InlineKeyboardButton("👤 Falar com Atendente", callback_data="atendimento_humanizado")]
    ])
    
    await query.edit_message_text(texto, parse_mode="HTML", reply_markup=teclado)


# ==========================================
# VERIFICAÇÃO DE CHAMADOS
# ==========================================

async def ver_meus_chamados(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Permite ao usuário ver seus chamados de suporte."""
    query = update.callback_query
    await query.answer()
    
    chat_id = str(update.effective_user.id)
    
    try:
        res = supabase.table("chamados_suporte").select("*").eq("chat_id", chat_id).order("created_at", desc=True).limit(5).execute()
        
        if not res.data:
            await query.edit_message_text(
                "📋 Você não possui chamados registrados.\n\n"
                "Se precisar de ajuda, utilize o botão abaixo:",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("👤 Abrir Chamado", callback_data="atendimento_humanizado")],
                    [InlineKeyboardButton("⬅️ Voltar", callback_data="atendimento_menu")]
                ])
            )
            return
        
        texto = "📋 <b>Seus Últimos Chamados:</b>\n\n"
        
        for chamado in res.data[:5]:
            status_emoji = {
                "aberto": "🟢",
                "em_andamento": "🟡",
                "respondido": "🔵",
                "resolvido": "✅",
                "fechado": "⚫"
            }.get(chamado["status"], "⚪")
            
            texto += (
                f"{status_emoji} <b>Chamado #{chamado['id']}</b>\n"
                f"📝 {chamado['mensagem'][:50]}...\n"
                f"📅 {chamado['created_at'][:10]}\n\n"
            )
        
        texto += "Para mais detalhes, fale com nossa equipe!"
        
        await query.edit_message_text(
            texto,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👤 Novo Chamado", callback_data="atendimento_humanizado")],
                [InlineKeyboardButton("⬅️ Voltar", callback_data="atendimento_menu")]
            ])
        )
        
    except Exception as e:
        logger.error(f"Erro ao listar chamados: {e}")
        await query.edit_message_text("❌ Erro ao buscar seus chamados.")


# ==========================================
# COMANDOS DO ADMINISTRADOR
# ==========================================

async def comando_ver_chamados(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando para administrador ver todos os chamados abertos."""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Acesso restrito a administradores.")
        return
    
    chamados = await listar_chamados_abertos()
    
    if not chamados:
        await update.message.reply_text("✅ Nenhum chamado aberto no momento.")
        return
    
    texto = "📋 <b>CHAMADOS ABERTOS</b>\n\n"
    
    for chamado in chamados[:10]:
        texto += (
            f"🔔 <b>Chamado #{chamado['id']}</b>\n"
            f"👤 {chamado['nome_usuario']} (ID: {chamado['chat_id']})\n"
            f"📝 {chamado['mensagem'][:100]}\n"
            f"📅 {chamado['created_at']}\n"
            f"➡️ Para responder: <code>/responder {chamado['id']} sua_resposta</code>\n\n"
        )
    
    await update.message.reply_text(texto, parse_mode="HTML")


async def comando_responder_chamado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando para administrador responder um chamado."""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Acesso restrito a administradores.")
        return
    
    if len(context.args) < 2:
        await update.message.reply_text(
            "⚠️ Uso correto: <code>/responder [ID_CHAMADO] [SUA_RESPOSTA]</code>",
            parse_mode="HTML"
        )
        return
    
    chamado_id = int(context.args[0])
    resposta = " ".join(context.args[1:])
    
    try:
        res = supabase.table("chamados_suporte").select("*").eq("id", chamado_id).execute()
        
        if not res.data:
            await update.message.reply_text("❌ Chamado não encontrado.")
            return
        
        chamado = res.data[0]
        chat_id_usuario = chamado["chat_id"]
        
        await responder_chamado(chamado_id, resposta, user_id)
        
        await context.bot.send_message(
            chat_id=chat_id_usuario,
            text=(
                "🔔 <b>RESPOSTA AO SEU CHAMADO</b>\n\n"
                f"📋 <b>Chamado:</b> #{chamado_id}\n\n"
                f"💬 <b>Nossa resposta:</b>\n{resposta}\n\n"
                "Se precisar de mais ajuda, responda esta mensagem!"
            ),
            parse_mode="HTML"
        )
        
        await registrar_historico(chat_id_usuario, "resposta_admin", resposta, "admin")
        
        await update.message.reply_text(f"✅ Resposta enviada ao usuário do chamado #{chamado_id}.")
        
    except Exception as e:
        logger.error(f"Erro ao responder chamado: {e}")
        await update.message.reply_text(f"❌ Erro ao responder chamado: {e}")


# ==========================================
# FUNÇÕES AUXILIARES
# ==========================================

async def listar_chamados_abertos() -> list:
    """Lista todos os chamados abertos para o administrador."""
    try:
        res = supabase.table("chamados_suporte").select("*").in_("status", ["aberto", "em_andamento"]).order("created_at", desc=True).execute()
        return res.data if res.data else []
        
    except Exception as e:
        logger.error(f"Erro ao listar chamados abertos: {e}")
        return []


async def responder_chamado(chamado_id: int, resposta_admin: str, atendente_id: str) -> bool:
    """Registra a resposta do administrador e atualiza o chamado."""
    try:
        from datetime import datetime, timezone
        agora = datetime.now(timezone.utc).isoformat()
        
        supabase.table("chamados_suporte").update({
            "status": "respondido",
            "resposta_admin": resposta_admin,
            "atendente_id": str(atendente_id),
            "respondido_em": agora
        }).eq("id", chamado_id).execute()
        
        return True
        
    except Exception as e:
        logger.error(f"Erro ao responder chamado: {e}")
        return False

# ==========================================
# RESPOSTAS DO FAQ
# ==========================================

async def faq_cadastrar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Resposta para Como cadastrar uma regulação."""
    query = update.callback_query
    await query.answer()
    texto = (
        "📌 <b>Como cadastrar uma nova regulação?</b>\n\n"
        "• Utilize o comando <b>/cadastrar_nova</b> no menu do bot.\n"
        "• Digite o número do seu <b>Cartão SUS</b> (15 dígitos) ou o <b>ID da Regulação</b>.\n"
        "• Siga as instruções na tela até a confirmação do cadastro."
    )
    teclado = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Voltar", callback_data="atendimento_faq")]])
    await query.edit_message_text(texto, parse_mode="HTML", reply_markup=teclado)


async def faq_consultar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Resposta para Como consultar minhas regulações."""
    query = update.callback_query
    await query.answer()
    texto = (
        "🔍 <b>Como consultar minhas regulações?</b>\n\n"
        "• Para ver todas as suas regulações: digite <b>/verificar_todos</b>.\n"
        "• Para consultar uma regulação específica: digite <b>/verificar_especifico</b>."
    )
    teclado = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Voltar", callback_data="atendimento_faq")]])
    await query.edit_message_text(texto, parse_mode="HTML", reply_markup=teclado)


async def faq_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Resposta para Onde encontrar o Cartão SUS ou ID."""
    query = update.callback_query
    await query.answer()
    texto = (
        "🆔 <b>Onde encontrar o Cartão SUS ou ID da Regulação?</b>\n\n"
        "• <b>Cartão SUS:</b> O número possui 15 dígitos e pode ser encontrado no seu cartão impresso ou no aplicativo 'Meu SUS Digital'.\n"
        "• <b>ID da Regulação:</b> É o código fornecido pelo posto de saúde ou hospital no momento da solicitação."
    )
    teclado = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Voltar", callback_data="atendimento_faq")]])
    await query.edit_message_text(texto, parse_mode="HTML", reply_markup=teclado)


async def faq_alterar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Resposta para Como alterar meus dados."""
    query = update.callback_query
    await query.answer()
    texto = (
        "✏️ <b>Como alterar ou corrigir dados?</b>\n\n"
        "• Para alterar informações de uma regulação já cadastrada, utilize o comando <b>/corrigir</b> no menu principal."
    )
    teclado = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Voltar", callback_data="atendimento_faq")]])
    await query.edit_message_text(texto, parse_mode="HTML", reply_markup=teclado)


async def faq_planos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Resposta para Planos e Assinaturas."""
    query = update.callback_query
    await query.answer()
    texto = (
        "💳 <b>Planos e Assinaturas</b>\n\n"
        "• Para verificar seus planos ativos, renovar ou fazer upgrade, acesse o comando <b>/planos</b> no menu principal."
    )
    teclado = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Voltar", callback_data="atendimento_faq")]])
    await query.edit_message_text(texto, parse_mode="HTML", reply_markup=teclado)


async def faq_governo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Resposta para O VigiaSaude tem vínculo com o governo."""
    query = update.callback_query
    await query.answer()
    texto = (
        "⚠️ <b>O VigiaSaude tem vínculo com o governo?</b>\n\n"
        "Não. O VigiaSaude é uma ferramenta <b>independente</b> e não possui vínculo oficial com a Prefeitura de Teresina, FMS ou SUS.\n"
        "As informações são baseadas nos dados públicos dos portais de regulação."
    )
    teclado = InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ Voltar", callback_data="atendimento_faq")]])
    await query.edit_message_text(texto, parse_mode="HTML", reply_markup=teclado)

# ==========================================
# PROCESSAR MENSAGEM GERAL (SEM CLICAR NO FAQ)
# ==========================================

async def processar_mensagem_geral(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processa qualquer mensagem enviada pelo usuário e tenta responder com IA (usando contexto)."""
    if not update.message or not update.message.text:
        return

    texto_usuario = update.message.text
    logger.info(f"📩 Mensagem recebida: {texto_usuario}")

    # Ignora comandos (ex: /start, /planos)
    if texto_usuario.startswith("/"):
        return

    # Verifica se o usuário está em um fluxo específico (cadastro, correção, etc.)
    if context.user_data.get("modo_atendimento") == "humanizado":
        return  # Não interfere no atendimento humanizado

    # 1. Busca contexto do usuário no Supabase
    chat_id = str(update.effective_user.id)
    contexto_usuario = await buscar_contexto_usuario(chat_id)

    # 2. Tenta encontrar resposta no FAQ estático
    resposta_faq = await buscar_faq_por_palavras_chave(texto_usuario)

    # 3. Se não encontrou no FAQ, tenta usar a IA com contexto
    if not resposta_faq:
        resposta_ia = await gerar_resposta_ia(
            texto_usuario,
            {
                "nome_usuario": update.effective_user.first_name,
                "chat_id": chat_id,
                "contexto_usuario": contexto_usuario
            }
        )
        if resposta_ia:
            resposta_faq = {"resposta": resposta_ia}

    # 4. Se encontrou resposta (FAQ ou IA), envia
    if resposta_faq:
        await registrar_historico(
            chat_id=chat_id,
            tipo="ia_automatica",
            mensagem=texto_usuario,
            origem="bot"
        )

        await update.message.reply_text(
            resposta_faq["resposta"],
            parse_mode="HTML"
        )

        # Oferece opções adicionais
        teclado = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("❓ FAQ Automático", callback_data="atendimento_faq"),
                InlineKeyboardButton("👤 Falar com Atendente", callback_data="atendimento_humanizado")
            ],
            [InlineKeyboardButton("📧 Email de Suporte", callback_data="atendimento_email")]
        ])

        await update.message.reply_text(
            "Posso ajudar com mais alguma coisa? Selecione uma opção abaixo:",
            reply_markup=teclado
        )
    else:
        # 5. Se nem FAQ nem IA responderam, NÃO abre chamado automaticamente.
        # Apenas informa que não entendeu e oferece opções ao usuário.
        teclado = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("❓ FAQ Automático", callback_data="atendimento_faq"),
                InlineKeyboardButton("👤 Falar com Atendente", callback_data="atendimento_humanizado")
            ],
            [InlineKeyboardButton("📧 Email de Suporte", callback_data="atendimento_email")]
        ])

        await update.message.reply_text(
            "🤔 Não consegui entender sua pergunta.\n\n"
            "Posso ajudar com dúvidas sobre cadastro, planos ou status de regulações.\n"
            "Se preferir, você pode falar com um atendente humano ou consultar as perguntas frequentes.",
            reply_markup=teclado
        )# ==========================================
# EXPORTAÇÃO
# ==========================================

__all__ = [
    "menu_atendimento",
    "iniciar_faq",
    "processar_pergunta_faq",
    "iniciar_atendimento_humanizado",
    "processar_mensagem_humanizado",
    "ver_meus_chamados",
    "comando_ver_chamados",
    "comando_responder_chamado",
    "cancelar_atendimento",
    "callback_email_suporte",
    "processar_mensagem_geral",  # <-- ADICIONE ESTA LINHA
    "AGUARDANDO_MENSAGEM_CHAMADO"
]
