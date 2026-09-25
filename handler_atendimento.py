# handler_atendimento.py
import logging
import asyncio
import re
from datetime import datetime, time as dtime      # ← ADICIONE ESTA LINHA
from zoneinfo import ZoneInfo
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from ia_atendimento import gerar_resposta_ia
from database_atendimento import (
    buscar_faq_por_palavras_chave,
    registrar_chamado_suporte,
    adicionar_mensagem_fila,
    registrar_historico,
    obter_email_suporte,
    buscar_contexto_usuario,
    buscar_estatisticas_admin,
)
from database import supabase

# Estados da conversa
AGUARDANDO_MENSAGEM_CHAMADO = 1
AGUARDANDO_RESPOSTA_USUARIO = 2
AGUARDANDO_RESPOSTA_ADMIN_RAPIDA = 3

def verificar_horario_comercial() -> dict:
    """
    Retorna um dict com:
      - dentro_horario: bool
      - mensagem: str (mensagem contextual para o usuário)
    """
    from datetime import datetime, time as dtime

    try:
        from zoneinfo import ZoneInfo
        agora = datetime.now(ZoneInfo("America/Sao_Paulo"))
    except Exception:
        agora = datetime.now()

    dia_semana = agora.weekday()  # 0=segunda ... 6=domingo
    hora_atual = agora.time()

    # Segunda a Sexta: 08h às 18h
    if dia_semana <= 4:
        if dtime(8, 0) <= hora_atual < dtime(18, 0):
            return {
                "dentro_horario": True,
                "mensagem": (
                    "✅ Estamos <b>em horário de atendimento</b>. "
                    "Nossa equipe responderá o mais breve possível."
                )
            }
        else:
            return {
                "dentro_horario": False,
                "mensagem": (
                    "⏰ <b>Estamos fora do horário de atendimento.</b>\n\n"
                    "Seu chamado será registrado e nossa equipe responderá "
                    "no próximo horário útil:\n"
                    "• Segunda a Sexta: 08h às 18h\n"
                    "• Sábado: 08h às 12h"
                )
            }

    # Sábado: 08h às 12h
    elif dia_semana == 5:
        if dtime(8, 0) <= hora_atual < dtime(12, 0):
            return {
                "dentro_horario": True,
                "mensagem": (
                    "✅ Estamos <b>em horário de atendimento</b>. "
                    "Nossa equipe responderá o mais breve possível."
                )
            }
        else:
            return {
                "dentro_horario": False,
                "mensagem": (
                    "⏰ <b>Estamos fora do horário de atendimento (sábado).</b>\n\n"
                    "Nosso atendimento no sábado é das 08h às 12h. "
                    "Seu chamado será registrado e respondido no próximo horário útil."
                )
            }

    # Domingo
    else:
        return {
            "dentro_horario": False,
            "mensagem": (
                "⏰ <b>Hoje é domingo e não temos atendimento.</b>\n\n"
                "Seu chamado será registrado e nossa equipe responderá "
                "na segunda-feira, a partir das 08h.\n\n"
                "Se for urgente, você pode enviar um email para "
                "suportevigiasaude@gmail.com."
            )
        }


try:
    from config import ADMIN_CHAT_ID
    ADMIN_ID = ADMIN_CHAT_ID or 5242040324
except ImportError:
    ADMIN_ID = 5242040324

logger = logging.getLogger(__name__)

try:
    from config import ADMIN_CHAT_ID
    ADMIN_ID = ADMIN_CHAT_ID or 5242040324
except ImportError:
    ADMIN_ID = 5242040324

logger = logging.getLogger(__name__)

# Estados da conversa
AGUARDANDO_MENSAGEM_CHAMADO = 1
AGUARDANDO_RESPOSTA_USUARIO = 2
AGUARDANDO_MIDIA_ADMIN = 3
AGUARDANDO_DESTINO_ADMIN = 4
AGUARDANDO_CONFIRMACAO_ENVIO = 5

def limpar_markdown(texto: str) -> str:
    """Remove marcadores de Markdown que ficam feios sem parse_mode."""
    if not texto:
        return texto
    texto = re.sub(r"\*\*(.+?)\*\*", r"\1", texto)
    texto = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"\1", texto)
    texto = re.sub(r"^#{1,6}\s*", "", texto, flags=re.MULTILINE)
    texto = re.sub(r"`(.+?)`", r"\1", texto)
    texto = re.sub(r"```.*?```", "", texto, flags=re.DOTALL)
    texto = re.sub(r"\n{3,}", "\n\n", texto)
    return texto.strip()


def escapar_html_seguro(texto: str) -> str:
    """Escapa apenas caracteres que quebram o parser HTML do Telegram,
    preservando tags básicas que a IA costuma usar (<b>, <i>, <code>)."""
    if not texto:
        return texto
    texto = texto.replace("&", "&amp;")
    texto = re.sub(r"<(?!/?(?:b|i|u|s|code|pre|a)(?:\s|>|/))", "&lt;", texto)
    texto = re.sub(r"(?<!>)>(?![a-zA-Z])", "&gt;", texto)
    return texto

# ==========================================
# MENU DE ATENDIMENTO
# ==========================================

async def menu_atendimento(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Menu principal - ações rápidas."""
    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Verificar Regulação", callback_data="atendimento_faq")],
        [InlineKeyboardButton("💳 Planos e Assinaturas", callback_data="atendimento_planos")],
        [
            InlineKeyboardButton("📧 Email de Suporte", callback_data="atendimento_email"),
            InlineKeyboardButton("👤 Atendente Humano", callback_data="atendimento_humanizado"),
        ],
        [InlineKeyboardButton("📖 Como funciona?", callback_data="sobre_vigia")],
    ])

    texto = (
        "🏠 <b>Menu Principal - VigiaSaúde</b>\n\n"
        "O que você deseja fazer?\n\n"
        "💡 <i>Você também pode digitar sua dúvida diretamente que eu respondo na hora.</i>"
    )

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(
                texto, parse_mode="HTML", reply_markup=teclado
            )
        except Exception:
            await update.callback_query.message.reply_text(
                texto, parse_mode="HTML", reply_markup=teclado
            )
    elif update.message:
        await update.message.reply_text(texto, parse_mode="HTML", reply_markup=teclado)

def _status_horario() -> str:
    """Retorna '🟢 Aberto agora' ou '🔴 Fechado agora'."""
    try:
        agora = datetime.now(ZoneInfo("America/Fortaleza"))
    except Exception:
        agora = datetime.now()
    
    dia = agora.weekday()  # 0=seg, 6=dom
    hora = agora.hour
    
    aberto = False
    if dia <= 4 and 8 <= hora < 18:      # Seg-Sex: 08h-18h
        aberto = True
    elif dia == 5 and 8 <= hora < 12:    # Sábado: 08h-12h
        aberto = True
    
    return "🟢 <b>Aberto agora</b>" if aberto else "🔴 <b>Fechado agora</b>"

async def comando_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Boas-vindas iniciais — mensagem diferenciada para admin e usuário comum."""
    from config import ADMIN_CHAT_ID as ADMIN_ID
    user = update.effective_user
    nome = user.first_name or "usuário"
    eh_admin = (user.id == ADMIN_ID)

    status = _status_horario()

    if eh_admin:
        # ═══════════ MENSAGEM DO ADMIN ═══════════
        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏛️ Central Admin", callback_data="adm_todos")],
            [InlineKeyboardButton("📊 Estatísticas", callback_data="adm_stats")],
            [InlineKeyboardButton("📖 Como funciona o VigiaSaúde?", callback_data="sobre_vigia")],
            [InlineKeyboardButton("🏠 Ir para o Menu Principal", callback_data="atendimento_menu")],
        ])

        texto = (
            f"🕐 <b>HORÁRIO DE ATENDIMENTO</b>  {status}\n"
            f"• Segunda a Sexta: <b>08h às 18h</b>\n"
            f"• Sábado: <b>08h às 12h</b>\n"
            f"• Domingo: <b>Fechado</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"

            f"👑 <b>PAINEL DO ADMINISTRADOR</b>\n\n"
            f"Olá, <b>{nome}</b>! Você está logado como <b>administrador</b>.\n\n"
            "🛠️ <b>Ferramentas disponíveis:</b>\n"
            "• <code>/admin</code> — Painel central de controle\n"
            "• <code>/chamados</code> — Ver chamados abertos\n"
            "• <code>/responder</code> — Responder a um chamado\n"
            "• <code>/enviar_midia</code> — Enviar imagem/documento\n"
            "• <code>/criar_enquete</code> — Criar enquete\n\n"
            "📌 <i>Use os botões abaixo para acesso rápido.</i>"
        )
    else:
        # ═══════════ MENSAGEM DO USUÁRIO COMUM ═══════════
        teclado = InlineKeyboardMarkup([
            [InlineKeyboardButton("📖 Como funciona o VigiaSaúde?", callback_data="sobre_vigia")],
            [InlineKeyboardButton("❓ Perguntas Frequentes", callback_data="atendimento_faq")],
            [InlineKeyboardButton("👤 Falar com Atendente", callback_data="atendimento_humanizado")],
            [InlineKeyboardButton("🏠 Ir para o Menu Principal", callback_data="atendimento_menu")],
        ])

        texto = (
            f"🕐 <b>HORÁRIO DE ATENDIMENTO</b>  {status}\n"
            f"• Segunda a Sexta: <b>08h às 18h</b>\n"
            f"• Sábado: <b>08h às 12h</b>\n"
            f"• Domingo: <b>Fechado</b>\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"

            f"👋 Olá, <b>{nome}</b>! Bem-vindo(a) ao <b>VigiaSaúde</b>!\n\n"
            "Sou o <b>VS</b>, seu assistente virtual. Aqui você pode:\n"
            "• Acompanhar o status das suas regulações\n"
            "• Tirar dúvidas sobre cadastro e planos\n"
            "• Consultar horários e informações\n\n"
            "⚠️ <i>Não realizo agendamento de consultas ou exames.</i>\n\n"
            "👉 Se é a primeira vez aqui, comece por <b>\"Como funciona o VigiaSaúde?\"</b>."
        )

    if update.message:
        await update.message.reply_text(texto, parse_mode="HTML", reply_markup=teclado)


async def comando_suporte(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exibe informações de contato e horário de suporte."""
    email = await obter_email_suporte()

    texto = (
        "📞 <b>Suporte VigiaSaúde</b>\n\n"
        f"📧 <b>Email:</b> {email}\n\n"
        "🕐 <b>Horário de atendimento:</b>\n"
        "• Segunda a Sexta: 08h às 18h\n"
        "• Sábado: 08h às 12h\n"
        "• Domingo: Fechado\n\n"
        "Para dúvidas rápidas, tente o FAQ automático. "
        "Para atendimento personalizado, fale com um atendente humano."
    )

    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Falar com Atendente", callback_data="atendimento_humanizado")],
        [InlineKeyboardButton("❓ FAQ Automático", callback_data="atendimento_faq")],
        [InlineKeyboardButton("⬅️ Menu Principal", callback_data="atendimento_menu")],
    ])

    if update.message:
        await update.message.reply_text(texto, parse_mode="HTML", reply_markup=teclado)

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
        # 2. IA primeiro — conversa natural
    is_admin = (update.effective_user.id == ADMIN_ID)
    resposta_ia = await gerar_resposta_ia(
        texto_usuario,
        {
            "nome_usuario": update.effective_user.first_name,
            "chat_id": chat_id,
            "contexto_usuario": contexto_usuario,
            "is_admin": is_admin
        }
    )

    if resposta_ia:
        resposta_faq = {"resposta": resposta_ia}
    else:
        # 3. Fallback: FAQ estático (só se a IA falhar)
        resposta_faq = await buscar_faq_por_palavras_chave(texto_usuario)

    # 4. Se encontrou resposta (FAQ ou IA), envia
    if resposta_faq:
        await registrar_historico(
            chat_id=chat_id,
            tipo="faq_automatico",
            mensagem=texto_usuario,
            origem="bot"
        )

        await update.message.reply_text(
        resposta_faq["resposta"]
        # Sem parse_mode — evita erro 400 quando a IA gera < > &
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
    """Inicia o atendimento humanizado, com mensagem contextual de horário."""

    horario = verificar_horario_comercial()

    texto = (
        "👤 <b>Atendimento Humanizado - VigiaSaúde</b>\n\n"
        "Você será atendido por nossa equipe especializada.\n\n"
        "Por favor, descreva sua dúvida ou problema abaixo.\n\n"
        f"{horario['mensagem']}\n\n"
        "<i>Digite sua mensagem agora:</i>"
    )

    if update.callback_query:
        query = update.callback_query
        await query.answer()
        await query.edit_message_text(texto, parse_mode="HTML")
    else:
        await update.message.reply_text(texto, parse_mode="HTML")

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
            teclado_admin = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("✍️ Responder", callback_data=f"adminresp_{chamado_id}"),
                    InlineKeyboardButton("✅ Finalizar", callback_data=f"adminfim_{chamado_id}"),
                ],
                [
                    InlineKeyboardButton("👁️ Ver detalhes", callback_data=f"adminver_{chamado_id}"),
                ],
            ])
            await context.bot.send_message(
                chat_id=ADMIN_ID,
                text=(
                    "🔔 <b>NOVO CHAMADO DE SUPORTE</b>\n\n"
                    f"📋 <b>Chamado ID:</b> <code>{chamado_id}</code>\n"
                    f"👤 <b>Usuário:</b> {nome_usuario}\n"
                    f"🆔 <b>Telegram ID:</b> <code>{chat_id}</code>\n"
                    f"📝 <b>Mensagem:</b>\n{mensagem}\n\n"
                    "👇 <b>Clique em ✍️ Responder para enviar a resposta.</b>"
                ),
                parse_mode="HTML",
                reply_markup=teclado_admin,
            )
        except Exception as e:
           logger.error(f"Erro ao notificar admin: {e}")

        # Confirma ao usuário
                # Confirma ao usuário
        horario = verificar_horario_comercial()
        if update.message:
            await update.message.reply_text(
                "✅ <b>Mensagem recebida com sucesso!</b>\n\n"
                f"Seu protocolo de atendimento é: <code>#{chamado_id}</code>\n\n"
                + (
                    "Nossa equipe está online e responderá em breve."
                    if horario["dentro_horario"]
                    else "Estamos fora do horário agora, mas sua mensagem será respondida no próximo horário útil."
                ) +
                "\n\n📧 Para contato direto, utilize nosso email: suportevigiasaude@gmail.com",
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
                    "Por favor, tente novamente ou contate: suportevigiasaude@gmail.com"
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
        "<b>suportevigiasaude@gmail.com</b>\n\n"
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

        # Botão para o usuário responder
        teclado_usuario = InlineKeyboardMarkup([
            [InlineKeyboardButton("✍️ Responder à Central", callback_data=f"responder_chamado_{chamado_id}")]
        ])

        await context.bot.send_message(
            chat_id=chat_id_usuario,
            text=(
                "🔔 <b>RESPOSTA AO SEU CHAMADO</b>\n\n"
                f"📋 <b>Chamado:</b> #{chamado_id}\n\n"
                f"💬 <b>Central VigiaSaúde:</b>\n{resposta}\n\n"
                "<i>Se precisar complementar ou responder, toque no botão abaixo.</i>"
            ),
            parse_mode="HTML",
            reply_markup=teclado_usuario
        )

        await registrar_historico(chat_id_usuario, "resposta_admin", resposta, "admin")

        # ✅ AGORA: mostra botões de ação para o ADMIN (finalizar, ver, etc)
        teclado_admin = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Finalizar Chamado", callback_data=f"adm_finalizar_{chamado_id}"),
                InlineKeyboardButton("👁️ Ver Chamado", callback_data=f"adm_ver_{chamado_id}"),
            ],
            [
                InlineKeyboardButton("📋 Ver Todos", callback_data="adm_todos"),
            ],
        ])

        await update.message.reply_text(
            f"✅ <b>Resposta enviada ao usuário do chamado #{chamado_id}.</b>\n\n"
            f"O que deseja fazer agora?",
            parse_mode="HTML",
            reply_markup=teclado_admin
        )

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
    """Processa qualquer mensagem enviada pelo usuário e tenta responder com IA."""
    # 🚩 Admin NÃO usa IA no Central — usa o Admin Bot para isso
    if update.effective_user.id == ADMIN_ID:
        return

    # 🚩 Se está em fluxo ativo, também NÃO processa
    if context.user_data.get("respondendo_chamado"):
        return
    if context.user_data.get("_em_fluxo_admin"):
        return

    texto_usuario = update.message.text
    logger.info(f"📩 Mensagem recebida: {texto_usuario}")

    # Ignora comandos (ex: /start, /planos)
    if texto_usuario.startswith("/"):
        return

    # Verifica se o usuário está em um fluxo específico
    if context.user_data.get("modo_atendimento") == "humanizado":
        return

    # 1. Busca contexto do usuário no Supabase
    chat_id = str(update.effective_user.id)
    contexto_usuario = await buscar_contexto_usuario(chat_id)
    is_admin = (update.effective_user.id == ADMIN_ID)

    # 1.1 Se for admin, busca estatísticas do sistema
    if is_admin:
        try:
            stats = await buscar_estatisticas_admin()
            contexto_usuario.update(stats)
        except Exception as e:
            logger.error(f"Erro ao buscar estatísticas do admin: {e}")

    # 2. Tenta encontrar resposta no FAQ estático
    resposta_faq = await buscar_faq_por_palavras_chave(texto_usuario)

    # 3. Se não encontrou no FAQ, tenta usar a IA com contexto
    if not resposta_faq:
        resposta_ia = await gerar_resposta_ia(
            texto_usuario,
            {
                "nome_usuario": update.effective_user.first_name,
                "chat_id": chat_id,
                "contexto_usuario": contexto_usuario,
                "is_admin": is_admin
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

        # Limpa Markdown e limita o tamanho (Telegram = 4096)
        texto_resposta = limpar_markdown(resposta_faq["resposta"])
        if len(texto_resposta) > 4000:
            texto_resposta = texto_resposta[:3990] + "\n\n[...]"

        # Tentativa 1: envio simples (sem parse_mode)
        try:
            await update.message.reply_text(texto_resposta)
        except Exception as e:
            logger.error(f"Falha ao enviar resposta (tentativa 1): {e}")
            try:
                texto_seguro = texto_resposta[:4000]
                await update.message.reply_text(texto_seguro)
            except Exception as e2:
                logger.error(f"Falha ao enviar resposta (tentativa 2): {e2}")

        # Oferece opções adicionais
        try:
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
        except Exception as e:
            logger.error(f"Falha ao enviar botões: {e}")

    else:
        # 5. Fallback para quando a IA não responde
        is_admin = (update.effective_user.id == ADMIN_ID)

        if is_admin:
            teclado = InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 Ver Chamados", callback_data="ver_chamados")],
                [InlineKeyboardButton("❓ FAQ Automático", callback_data="atendimento_faq")]
            ])
            await update.message.reply_text(
                "🤖 Não entendi. Como administrador, use /chamados ou o FAQ.",
                reply_markup=teclado
            )
        else:
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
            )

async def sobre_vigia_saude(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Explica o que é o VigiaSaúde e como funciona."""
    query = update.callback_query
    await query.answer()

    texto = (
        "📖 <b>Como funciona o VigiaSaúde?</b>\n\n"
        "O <b>VigiaSaúde</b> é uma ferramenta <b>independente</b> que ajuda você a "
        "acompanhar o status das suas regulações no SUS.\n\n"
        "✅ <b>O que ele FAZ:</b>\n"
        "• Consulta o status de regulações já cadastradas\n"
        "• Envia alertas quando há mudanças\n"
        "• Responde dúvidas sobre cadastro e planos\n\n"
        "❌ <b>O que ele NÃO FAZ:</b>\n"
        "• Não marca, agenda ou remarca consultas/exames\n"
        "• Não substitui a central de regulação do SUS\n\n"
        "⚠️ <b>Importante:</b> o VigiaSaúde não tem vínculo oficial com "
        "Prefeitura, FMS ou SUS."
    )

    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Consultar minhas regulações", callback_data="atendimento_faq")],
        [InlineKeyboardButton("💳 Ver planos", callback_data="atendimento_planos")],
        [InlineKeyboardButton("⬅️ Menu Principal", callback_data="atendimento_menu")],
    ])

    await query.edit_message_text(texto, parse_mode="HTML", reply_markup=teclado)


async def callback_planos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Exibe informações sobre planos (funciona via comando e via botão)."""
    
    texto = (
        "💳 <b>Planos VigiaSaúde</b>\n\n"
        "• <b>Degustação (Grátis)</b> – 7 dias de validade\n"
        "• <b>Trimestral</b> – R$ 9,99\n"
        "• <b>Semestral</b> – R$ 14,99\n\n"
        "💠 <b>Pagamento:</b> Pix (QR Code ou Copia e Cola)\n\n"
        "Para assinar, entre em contato com o suporte abaixo."
    )

    teclado = InlineKeyboardMarkup([
        [InlineKeyboardButton("📧 Falar com Suporte", callback_data="atendimento_email")],
        [InlineKeyboardButton("⬅️ Menu Principal", callback_data="atendimento_menu")],
    ])

    if update.callback_query:
        await update.callback_query.answer()
        try:
            await update.callback_query.edit_message_text(
                texto, parse_mode="HTML", reply_markup=teclado
            )
        except Exception as e:
            if "Message is not modified" in str(e):
                return
            await update.callback_query.message.reply_text(
                texto, parse_mode="HTML", reply_markup=teclado
            )
    elif update.message:
        await update.message.reply_text(
            texto, parse_mode="HTML", reply_markup=teclado
        )

async def iniciar_resposta_usuario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Usuário clicou em 'Responder à Central' - inicia conversa para receber a resposta."""
    query = update.callback_query
    await query.answer()

    # Extrai o ID do chamado do callback_data
    chamado_id = int(query.data.split("_")[-1])
    context.user_data["respondendo_chamado_id"] = chamado_id
    context.user_data["_em_fluxo_admin"] = "responder_chamado"
    context.user_data["modo_atendimento"] = "respondendo_chamado"

    await query.edit_message_text(
        f"✍️ <b>Responder ao Chamado #{chamado_id}</b>\n\n"
        "Digite abaixo a sua mensagem. Ela será enviada para a nossa central.",
        parse_mode="HTML"
    )
    return AGUARDANDO_RESPOSTA_USUARIO


async def receber_resposta_usuario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recebe a mensagem do usuário e adiciona na fila do chamado."""
    if not update.message or not update.message.text:
        return ConversationHandler.END

    chat_id = str(update.effective_user.id)
    nome_usuario = update.effective_user.first_name or "Usuário"
    mensagem = update.message.text
    chamado_id = context.user_data.get("respondendo_chamado_id")

    if not chamado_id:
        await update.message.reply_text("❌ Não identifiquei o chamado. Tente novamente.")
        return ConversationHandler.END

    # Adiciona a resposta na fila
    await adicionar_mensagem_fila(chamado_id, chat_id, mensagem, "usuario")

    # Atualiza o status do chamado
    try:
        supabase.table("chamados_suporte").update({
            "status": "em_andamento"
        }).eq("id", chamado_id).execute()
    except Exception as e:
        logger.error(f"Erro ao atualizar status do chamado: {e}")

    # Notifica o admin
    try:
        await context.bot.send_message(
            chat_id=ADMIN_ID,
            text=(
                "🔔 <b>NOVA RESPOSTA DO USUÁRIO</b>\n\n"
                f"📋 <b>Chamado:</b> #{chamado_id}\n"
                f"👤 <b>Usuário:</b> {nome_usuario} (ID: <code>{chat_id}</code>)\n\n"
                f"💬 <b>Mensagem:</b>\n{mensagem}\n\n"
                f"➡️ Para responder: <code>/responder {chamado_id} sua_resposta</code>"
            ),
            parse_mode="HTML"
        )
    except Exception as e:
        logger.error(f"Erro ao notificar admin: {e}")

    await update.message.reply_text(
        "✅ <b>Mensagem enviada!</b>\n\n"
        "Nossa central receberá sua resposta e continuará o atendimento.",
        parse_mode="HTML"
    )

    context.user_data.pop("respondendo_chamado_id", None)
    context.user_data.pop("modo_atendimento", None)
    return ConversationHandler.END

    from datetime import datetime, time as dtime

    # ==========================================
# ENVIO DE MÍDIA (ADMIN) - POSTS E DOCUMENTOS
# ==========================================

async def iniciar_envio_midia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Inicia o fluxo de envio de mídia (admin)."""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Acesso restrito a administradores.")
        return ConversationHandler.END

    await update.message.reply_text(
        "📤 <b>Envio de Mídia</b>\n\n"
        "Envie a <b>imagem</b> ou o <b>documento</b> que deseja distribuir.\n"
        "Você pode adicionar uma <b>legenda</b> na própria mensagem.\n\n"
        "Para cancelar, use /cancelar.",
        parse_mode="HTML"
    )
    return AGUARDANDO_MIDIA_ADMIN


async def receber_midia_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recebe a mídia do admin e pede o destino."""
    msg = update.message

    if msg.photo:
        # Pega a maior resolução
        file_id = msg.photo[-1].file_id
        tipo = "photo"
    elif msg.document:
        file_id = msg.document.file_id
        tipo = "document"
    elif msg.video:
        file_id = msg.video.file_id
        tipo = "video"
    else:
        await msg.reply_text(
            "❌ Formato não suportado. Envie uma imagem, documento ou vídeo."
        )
        return AGUARDANDO_MIDIA_ADMIN

    context.user_data["midia_file_id"] = file_id
    context.user_data["midia_tipo"] = tipo
    context.user_data["midia_caption"] = msg.caption or ""

    await msg.reply_text(
        f"✅ Mídia recebida ({tipo}).\n\n"
        "📨 Para quem deseja enviar?\n\n"
        "• Digite o <b>ID do chat</b> (ex: <code>123456789</code>)\n"
        "• Ou digite <b>todos</b> para enviar a todos os usuários cadastrados.",
        parse_mode="HTML"
    )
    return AGUARDANDO_DESTINO_ADMIN


async def receber_destino_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recebe o destino (ID ou 'todos') e pede confirmação."""
    destino = update.message.text.strip().lower()

    if destino == "todos":
        # Busca todos os chat_ids únicos na tabela de assinaturas
        try:
            res = supabase.table("assinaturas").select("chat_id").execute()
            chat_ids = list(set(str(row["chat_id"]) for row in res.data if row.get("chat_id")))
        except Exception as e:
            logger.error(f"Erro ao buscar chat_ids: {e}")
            await update.message.reply_text("❌ Erro ao buscar lista de usuários.")
            return ConversationHandler.END

        if not chat_ids:
            await update.message.reply_text("⚠️ Nenhum usuário cadastrado encontrado.")
            return ConversationHandler.END

        context.user_data["destino_chat_ids"] = chat_ids
        alvo_texto = f"<b>TODOS os usuários</b> ({len(chat_ids)} destinatários)"

    else:
        # Tenta interpretar como chat_id
        try:
            chat_id_unico = str(int(destino))
        except ValueError:
            await update.message.reply_text(
                "❌ Destino inválido. Envie um ID numérico ou a palavra <b>todos</b>.",
                parse_mode="HTML"
            )
            return AGUARDANDO_DESTINO_ADMIN

        context.user_data["destino_chat_ids"] = [chat_id_unico]
        alvo_texto = f"Chat ID <code>{chat_id_unico}</code>"

    teclado = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Confirmar envio", callback_data="confirmar_envio_midia"),
            InlineKeyboardButton("❌ Cancelar", callback_data="cancelar_envio_midia"),
        ]
    ])

    caption = context.user_data.get("midia_caption") or "<i>(sem legenda)</i>"
    tipo = context.user_data.get("midia_tipo")

    await update.message.reply_text(
        "📋 <b>Confirmação de envio</b>\n\n"
        f"• Tipo: <b>{tipo}</b>\n"
        f"• Destino: {alvo_texto}\n"
        f"• Legenda: {caption}\n\n"
        "Confirma o envio?",
        parse_mode="HTML",
        reply_markup=teclado
    )
    return AGUARDANDO_CONFIRMACAO_ENVIO


async def confirmar_envio_midia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback: confirma e realiza o envio."""
    query = update.callback_query
    await query.answer()

    file_id = context.user_data.get("midia_file_id")
    tipo = context.user_data.get("midia_tipo")
    caption = context.user_data.get("midia_caption") or ""
    destinos = context.user_data.get("destino_chat_ids") or []

    if not file_id or not destinos:
        await query.edit_message_text("❌ Dados de envio incompletos. Recomece com /enviar_midia.")
        return ConversationHandler.END

    await query.edit_message_text(
        f"📤 Enviando para {len(destinos)} destinatário(s)...\nAguarde."
    )

    enviados = 0
    falhas = 0

    for chat_id in destinos:
        try:
            if tipo == "photo":
                await context.bot.send_photo(
                    chat_id=chat_id, photo=file_id,
                    caption=caption or None, parse_mode="HTML" if caption else None
                )
            elif tipo == "document":
                await context.bot.send_document(
                    chat_id=chat_id, document=file_id,
                    caption=caption or None, parse_mode="HTML" if caption else None
                )
            elif tipo == "video":
                await context.bot.send_video(
                    chat_id=chat_id, video=file_id,
                    caption=caption or None, parse_mode="HTML" if caption else None
                )
            enviados += 1
        except Exception as e:
            falhas += 1
            logger.error(f"Erro ao enviar para {chat_id}: {e}")

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            "✅ <b>Envio concluído</b>\n\n"
            f"• Enviados com sucesso: {enviados}\n"
            f"• Falhas: {falhas}"
        ),
        parse_mode="HTML"
    )

    # Limpa dados
    for k in ("midia_file_id", "midia_tipo", "midia_caption", "destino_chat_ids"):
        context.user_data.pop(k, None)

    return ConversationHandler.END


async def cancelar_envio_midia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback: cancela o envio."""
    query = update.callback_query
    await query.answer()

    for k in ("midia_file_id", "midia_tipo", "midia_caption", "destino_chat_ids"):
        context.user_data.pop(k, None)

    await query.edit_message_text("❌ Envio cancelado.")
    return ConversationHandler.END

async def comando_finalizar_chamado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando para admin finalizar um chamado diretamente pelo ID."""
    user_id = update.effective_user.id

    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Acesso restrito a administradores.")
        return

    if not context.args:
        await update.message.reply_text(
            "⚠️ Uso correto: <code>/finalizar [ID_CHAMADO]</code>\n"
            "Exemplo: <code>/finalizar 45</code>",
            parse_mode="HTML"
        )
        return

    try:
        chamado_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("❌ ID inválido.")
        return

    try:
        # Busca o chamado
        res = supabase.table("chamados_suporte").select("*").eq("id", chamado_id).execute()
        if not res.data:
            await update.message.reply_text(f"❌ Chamado #{chamado_id} não encontrado.")
            return

        chamado = res.data[0]

        # Atualiza status
        supabase.table("chamados_suporte").update({
            "status": "fechado"
        }).eq("id", chamado_id).execute()

        # Notifica o usuário
        try:
            await context.bot.send_message(
                chat_id=chamado["chat_id"],
                text=(
                    f"✅ <b>Seu chamado #{chamado_id} foi finalizado.</b>\n\n"
                    "Obrigado pelo contato! Se precisar, é só chamar de novo."
                ),
                parse_mode="HTML"
            )
        except Exception:
            pass

        await update.message.reply_text(
            f"✅ <b>Chamado #{chamado_id} finalizado com sucesso.</b>",
            parse_mode="HTML"
        )

    except Exception as e:
        logger.error(f"Erro ao finalizar chamado: {e}")
        await update.message.reply_text(f"❌ Erro ao finalizar chamado: {e}")

# ==========================================
# RESPOSTA RÁPIDA — VIA BOTÕES
# ==========================================

async def callback_iniciar_resposta(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin clicou em '✍️ Responder' — inicia modo de resposta."""
    query = update.callback_query
    await query.answer()

    if update.effective_user.id != ADMIN_ID:
        return

    # Extrai ID do chamado
    chamado_id = int(query.data.replace("adminresp_", ""))

    # Salva no contexto
    context.user_data["respondendo_chamado_id"] = chamado_id

    # Edita a mensagem para indicar modo ativo
    try:
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton(f"✍️ Modo de resposta ativo (Chamado #{chamado_id})", callback_data="noop")]
        ]))
    except Exception:
        pass

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=(
            f"✍️ <b>Respondendo ao Chamado #{chamado_id}</b>\n\n"
            "Digite abaixo a mensagem que será enviada ao usuário.\n\n"
            "<i>Para cancelar, envie /cancelar.</i>"
        ),
        parse_mode="HTML",
    )
    return AGUARDANDO_RESPOSTA_ADMIN_RAPIDA


async def receber_resposta_rapida(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Recebe o texto do admin e envia ao usuário."""
    if update.effective_user.id != ADMIN_ID:
        return ConversationHandler.END

    if not update.message or not update.message.text:
        return AGUARDANDO_RESPOSTA_ADMIN_RAPIDA

    texto = update.message.text.strip()
    if texto.startswith("/"):
        return AGUARDANDO_RESPOSTA_ADMIN_RAPIDA

    chamado_id = context.user_data.get("respondendo_chamado_id")
    if not chamado_id:
        await update.message.reply_text("❌ Chamado não identificado. Use o botão novamente.")
        return ConversationHandler.END

    try:
        # Busca o chamado
        res = supabase.table("chamados_suporte").select("*").eq("id", chamado_id).execute()
        if not res.data:
            await update.message.reply_text(f"❌ Chamado #{chamado_id} não encontrado.")
            return ConversationHandler.END

        chamado = res.data[0]
        chat_id_usuario = chamado["chat_id"]

        # Atualiza status
        from datetime import datetime, timezone
        agora = datetime.now(timezone.utc).isoformat()
        supabase.table("chamados_suporte").update({
            "status": "respondido",
            "resposta_admin": texto,
            "atendente_id": str(ADMIN_ID),
            "respondido_em": agora,
        }).eq("id", chamado_id).execute()

        # Envia para o usuário
        await context.bot.send_message(
            chat_id=chat_id_usuario,
            text=(
                "🔔 <b>RESPOSTA AO SEU CHAMADO</b>\n\n"
                f"📋 <b>Chamado:</b> #{chamado_id}\n\n"
                f"💬 <b>Central VigiaSaúde:</b>\n{texto}\n\n"
                "<i>Se precisar complementar, toque no botão abaixo.</i>"
            ),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✍️ Responder à Central", callback_data=f"responder_chamado_{chamado_id}")]
            ]),
        )

        # Confirma para o admin
        await update.message.reply_text(
            f"✅ <b>Resposta enviada!</b>\n\n"
            f"Chamado #{chamado_id} foi respondido com sucesso.",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Erro ao enviar resposta rápida: {e}")
        await update.message.reply_text(f"❌ Erro: {e}")

        context.user_data.pop("respondendo_chamado_id", None)

    # 🚩 Limpa o flag APÓS 2s (para o group=2 ainda ver durante o mesmo update)
    async def _limpar_flag_depois(ctx):
        await asyncio.sleep(2)
        ctx.user_data.pop("_em_fluxo_admin", None)

    if context.application:
        context.application.create_task(_limpar_flag_depois(context))
    else:
            context.user_data.pop("respondendo_chamado_id", None)

    # 🚩 Limpa o flag APÓS 2s (para o group=2 ainda ver durante o mesmo update)
    async def _limpar_flag_depois(ctx):
        await asyncio.sleep(2)
        ctx.user_data.pop("_em_fluxo_admin", None)

    if context.application:
        context.application.create_task(_limpar_flag_depois(context))
    else:
        context.user_data.pop("_em_fluxo_admin", None)

    return ConversationHandler.END

    return ConversationHandler.END


async def callback_finalizar_chamado(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin clicou em '✅ Finalizar'."""
    query = update.callback_query
    await query.answer()

    if update.effective_user.id != ADMIN_ID:
        return

    chamado_id = int(query.data.replace("adminfim_", ""))

    try:
        # Busca
        res = supabase.table("chamados_suporte").select("*").eq("id", chamado_id).execute()
        if not res.data:
            await query.edit_message_text("❌ Chamado não encontrado.")
            return

        chamado = res.data[0]

        # Atualiza
        supabase.table("chamados_suporte").update({"status": "fechado"}).eq("id", chamado_id).execute()

        # Notifica o usuário
        try:
            await context.bot.send_message(
                chat_id=chamado["chat_id"],
                text=f"✅ <b>Seu chamado #{chamado_id} foi finalizado.</b>\n\nObrigado pelo contato!",
                parse_mode="HTML",
            )
        except Exception:
            pass

        await query.edit_message_text(
            f"✅ <b>Chamado #{chamado_id} finalizado.</b>",
            parse_mode="HTML",
        )
    except Exception as e:
        logger.error(f"Erro ao finalizar: {e}")
        await query.edit_message_text(f"❌ Erro: {e}")


async def callback_ver_detalhes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin clicou em '👁️ Ver detalhes'."""
    query = update.callback_query
    await query.answer()

    if update.effective_user.id != ADMIN_ID:
        return

    chamado_id = int(query.data.replace("adminver_", ""))

    try:
        res = supabase.table("chamados_suporte").select("*").eq("id", chamado_id).execute()
        if not res.data:
            await query.answer("❌ Não encontrado", show_alert=True)
            return

        c = res.data[0]
        texto = (
            f"📋 <b>Chamado #{c.get('id')}</b>\n\n"
            f"👤 <b>Usuário:</b> {c.get('nome_usuario', '?')}\n"
            f"🆔 <b>Chat ID:</b> <code>{c.get('chat_id')}</code>\n"
            f"📊 <b>Status:</b> {c.get('status')}\n"
            f"📅 <b>Criado:</b> {c.get('created_at', '')[:19]}\n\n"
            f"📝 <b>Mensagem:</b>\n{c.get('mensagem', '')}\n"
        )
        if c.get("resposta_admin"):
            texto += f"\n\n✅ <b>Sua resposta:</b>\n{c.get('resposta_admin')}"

        await context.bot.send_message(chat_id=ADMIN_ID, text=texto, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Erro ao ver detalhes: {e}")


async def cancelar_resposta_rapida(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancela o modo de resposta."""
    context.user_data.pop("respondendo_chamado_id", None)

    # 🚩 Limpa o flag APÓS 2s
    async def _limpar_flag_depois(ctx):
        await asyncio.sleep(2)
        ctx.user_data.pop("_em_fluxo_admin", None)

    if context.application:
        context.application.create_task(_limpar_flag_depois(context))
    else:
        context.user_data.pop("_em_fluxo_admin", None)

    if update.message:
        await update.message.reply_text("❌ Resposta cancelada.")
    return ConversationHandler.END


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
    "AGUARDANDO_MENSAGEM_CHAMADO",
    # NOVOS
    "callback_iniciar_resposta",
    "receber_resposta_rapida",
    "callback_finalizar_chamado",
    "callback_ver_detalhes",
    "cancelar_resposta_rapida",
    "AGUARDANDO_RESPOSTA_ADMIN_RAPIDA",
]