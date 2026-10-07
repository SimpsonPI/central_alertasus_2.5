from dotenv import load_dotenv
load_dotenv()

import os
import logging
import asyncio
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from telegram import (
    BotCommand,
    BotCommandScopeAllPrivateChats,
    BotCommandScopeChat,
)
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from config import TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID
from handler_atendimento import (
    menu_atendimento,
    comando_start,
    comando_suporte,
    sobre_vigia_saude,
    callback_planos,
    iniciar_faq,
    processar_pergunta_faq,
    iniciar_atendimento_humanizado,
    processar_mensagem_humanizado,
    ver_meus_chamados,
    comando_ver_chamados,
    comando_responder_chamado,
    comando_finalizar_chamado,
    cancelar_atendimento,
    callback_email_suporte,
    processar_mensagem_geral,
    iniciar_resposta_usuario,
    receber_resposta_usuario,
    processar_avaliacao,
    verificar_chamados_para_avaliar,
    AGUARDANDO_MENSAGEM_CHAMADO,
    AGUARDANDO_RESPOSTA_USUARIO,
    callback_iniciar_resposta,
    receber_resposta_rapida,
    callback_finalizar_chamado,
    callback_ver_detalhes,
    cancelar_resposta_rapida,
    AGUARDANDO_RESPOSTA_ADMIN_RAPIDA,
    faq_cadastrar,
    faq_consultar,
    faq_id,
    faq_alterar,
    faq_planos,
    faq_governo,
)

from admin_handlers import (
    ADMIN_IDS,
    menu_admin,
    callback_listar,
    callback_estatisticas,
    callback_voltar,
    callback_ver_chamado,
    callback_responder,
    receber_resposta_admin,
    cancelar_resposta_admin,
    callback_cancelar_resposta,
    callback_finalizar,
    AGUARDANDO_RESPOSTA_ADMIN,
)

from admin_atendimento import comando_avaliacoes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def erro_global_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(msg="Exceção capturada pelo bot:", exc_info=context.error)


async def configurar_comandos(app):
    """Configura comandos do Telegram e agenda tarefas periódicas."""
    comandos = [
        BotCommand("start", "Iniciar atendimento"),
        BotCommand("menu", "Menu principal"),
        BotCommand("faq", "Perguntas frequentes"),
        BotCommand("atendimento", "Falar com atendente"),
        BotCommand("suporte", "Canais de suporte"),
    ]

    try:
        await app.bot.set_my_commands(
            comandos,
            scope=BotCommandScopeAllPrivateChats(),
        )
    except Exception as e:
        logger.error(f"Erro ao configurar comandos: {e}")

    # Job periódico: pesquisa de satisfação a cada 5 min
    job_queue = app.job_queue
    if job_queue:
        job_queue.run_repeating(
            lambda _: asyncio.create_task(
                verificar_chamados_para_avaliar(app)
            ),
            interval=300,
            first=120,
        )
        logger.info("✅ Job de pesquisa de satisfação agendado (5 min)")


def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN") or TELEGRAM_BOT_TOKEN
    app = (
        ApplicationBuilder()
        .token(token)
        .post_init(configurar_comandos)
        .build()
    )

    app.add_error_handler(erro_global_handler)

    # ─── ConversationHandler: Atendimento Humanizado ───
    conv_atendimento_humanizado = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(iniciar_atendimento_humanizado, pattern="^atendimento_humanizado$"),
            CommandHandler("atendimento", iniciar_atendimento_humanizado),
        ],
        states={
            AGUARDANDO_MENSAGEM_CHAMADO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, processar_mensagem_humanizado)
            ],
        },
        fallbacks=[
            CommandHandler("cancelar", cancelar_atendimento),
            CallbackQueryHandler(cancelar_atendimento, pattern="^cancelar_atendimento$"),
        ],
        per_message=False,
    )

    # ─── ConversationHandler: Resposta do usuário ao chamado ───
    conv_resposta_usuario = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(iniciar_resposta_usuario, pattern="^responder_chamado_\\d+$"),
        ],
        states={
            AGUARDANDO_RESPOSTA_USUARIO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receber_resposta_usuario)
            ],
        },
        fallbacks=[
            CommandHandler("cancelar", cancelar_atendimento),
        ],
        per_message=False,
    )

    # ─── ConversationHandler: Resposta rápida admin (botões adminresp_) ───
    conv_resposta_rapida = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(callback_iniciar_resposta, pattern="^adminresp_\\d+$"),
        ],
        states={
            AGUARDANDO_RESPOSTA_ADMIN_RAPIDA: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receber_resposta_rapida),
            ],
        },
        fallbacks=[
            CommandHandler("cancelar", cancelar_resposta_rapida),
        ],
        per_message=False,
    )

    # ─── ConversationHandler: Resposta admin (via painel adm_) ───
    conv_resposta_admin = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(callback_responder, pattern=r"^adm_responder_\d+$")
        ],
        states={
            AGUARDANDO_RESPOSTA_ADMIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receber_resposta_admin)
            ],
        },
        fallbacks=[
            CommandHandler("cancelar_admin", cancelar_resposta_admin)
        ],
        per_message=False,
    )

    # ─── Registra TODOS os ConversationHandlers ───
    app.add_handler(conv_atendimento_humanizado)
    app.add_handler(conv_resposta_usuario)
    app.add_handler(conv_resposta_rapida)
    app.add_handler(conv_resposta_admin)

    # ─── Comandos ───
    app.add_handler(CommandHandler("start", comando_start))
    app.add_handler(CommandHandler("menu", menu_atendimento))
    app.add_handler(CommandHandler("faq", iniciar_faq))
    app.add_handler(CommandHandler("suporte", comando_suporte))
    app.add_handler(CommandHandler("chamados", comando_ver_chamados))
    app.add_handler(CommandHandler("responder", comando_responder_chamado))
    app.add_handler(CommandHandler("finalizar", comando_finalizar_chamado))
    app.add_handler(CommandHandler("admin", menu_admin))
    app.add_handler(CommandHandler("planos", callback_planos))
    app.add_handler(CommandHandler("avaliacoes", comando_avaliacoes))

    # ─── Callbacks gerais ───
    app.add_handler(CallbackQueryHandler(menu_atendimento, pattern="^atendimento_menu$"))
    app.add_handler(CallbackQueryHandler(iniciar_faq, pattern="^atendimento_faq$"))
    app.add_handler(CallbackQueryHandler(ver_meus_chamados, pattern="^ver_chamados$"))
    app.add_handler(CallbackQueryHandler(callback_email_suporte, pattern="^atendimento_email$"))
    app.add_handler(CallbackQueryHandler(cancelar_atendimento, pattern="^cancelar_atendimento$"))
    app.add_handler(CallbackQueryHandler(menu_atendimento, pattern="^iniciar$"))
    app.add_handler(CallbackQueryHandler(sobre_vigia_saude, pattern="^sobre_vigia$"))
    app.add_handler(CallbackQueryHandler(callback_planos, pattern="^atendimento_planos$"))

    # ─── Callbacks rápidos do admin (finalizar / ver detalhes) ───
    app.add_handler(CallbackQueryHandler(callback_finalizar_chamado, pattern="^adminfim_\\d+$"))
    app.add_handler(CallbackQueryHandler(callback_ver_detalhes, pattern="^adminver_\\d+$"))

    # ─── Callbacks de avaliação ───
    app.add_handler(CallbackQueryHandler(processar_avaliacao, pattern="^avaliar_"))

    # ─── Callbacks do FAQ ───
    app.add_handler(CallbackQueryHandler(faq_cadastrar, pattern="^faq_cadastrar$"))
    app.add_handler(CallbackQueryHandler(faq_consultar, pattern="^faq_consultar$"))
    app.add_handler(CallbackQueryHandler(faq_id, pattern="^faq_id$"))
    app.add_handler(CallbackQueryHandler(faq_alterar, pattern="^faq_alterar$"))
    app.add_handler(CallbackQueryHandler(faq_planos, pattern="^faq_planos$"))
    app.add_handler(CallbackQueryHandler(faq_governo, pattern="^faq_governo$"))

    # ─── Callbacks do painel admin ───
    app.add_handler(CallbackQueryHandler(callback_listar, pattern=r"^adm_(todos|aberto|em_atend)$"))
    app.add_handler(CallbackQueryHandler(callback_estatisticas, pattern=r"^adm_stats$"))
    app.add_handler(CallbackQueryHandler(callback_ver_chamado, pattern=r"^adm_ver_\d+$"))
    app.add_handler(CallbackQueryHandler(callback_voltar, pattern=r"^adm_voltar$"))
    app.add_handler(CallbackQueryHandler(callback_finalizar, pattern=r"^adm_finalizar_\d+$"))
    app.add_handler(CallbackQueryHandler(callback_cancelar_resposta, pattern=r"^adm_cancelar_resp_\d+$"))

    # ─── Handler global para mensagens (IA automática) ───
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, processar_mensagem_geral),
        group=2,
    )

    # ─── Servidor HTTP auxiliar (Railway) ───
    PORT = int(os.environ.get("PORT", "8080"))

    class SimpleHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Central VigiaSaude is running!")

    def run_http_server(port):
        server = HTTPServer(("0.0.0.0", port), SimpleHandler)
        server.serve_forever()

    threading.Thread(target=run_http_server, args=(PORT,), daemon=True).start()
    logger.info(f"Servidor HTTP auxiliar rodando na porta {PORT}")

    # ─── Última linha do main() ───
    logger.info("Iniciando a Central de Atendimento VigiaSaude via polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()