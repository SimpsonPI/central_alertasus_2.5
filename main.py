from dotenv import load_dotenv
load_dotenv()

import os
import logging
# ... resto dos imports
import os
import logging
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
    cancelar_atendimento,
    callback_email_suporte,
    processar_mensagem_geral,
    iniciar_resposta_usuario,
    receber_resposta_usuario,
    AGUARDANDO_MENSAGEM_CHAMADO,
    AGUARDANDO_RESPOSTA_USUARIO,
    faq_cadastrar,
    faq_consultar,
    faq_id,
    faq_alterar,
    faq_planos,
    faq_governo,
    iniciar_envio_midia,
    receber_midia_admin,
    receber_destino_admin,
    confirmar_envio_midia,
    cancelar_envio_midia,
    AGUARDANDO_MIDIA_ADMIN,
    AGUARDANDO_DESTINO_ADMIN,
    AGUARDANDO_CONFIRMACAO_ENVIO,
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
    callback_cancelar_resposta,      # ← ADICIONE ESTA LINHA
    callback_finalizar,
    AGUARDANDO_RESPOSTA_ADMIN,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def erro_global_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(msg="Exceção capturada pelo bot:", exc_info=context.error)


async def configurar_comandos(app):
    """Define os comandos do menu do Telegram, separando admin e usuário comum."""
    comandos_publicos = [
        BotCommand("start", "Iniciar atendimento"),
        BotCommand("menu", "Abrir menu principal"),
        BotCommand("faq", "Consultar FAQ automático"),
        BotCommand("atendimento", "Falar com atendente humano"),
        BotCommand("suporte", "Informações de suporte"),
    ]

    # Aplica a todos os chats privados
    try:
        await app.bot.set_my_commands(
            comandos_publicos,
            scope=BotCommandScopeAllPrivateChats(),
        )
    except Exception as e:
        logger.warning(f"Erro ao setar comandos públicos: {e}")

    # Comandos exclusivos do Admin
    if ADMIN_CHAT_ID:
        comandos_admin = comandos_publicos + [
            BotCommand("chamados", "Ver chamados abertos (admin)"),
            BotCommand("responder", "Responder chamado (admin)"),
            BotCommand("enviar_midia", "Enviar imagem/documento (admin)"),
            BotCommand("admin", "Central Admin"),
        ]
        try:
            await app.bot.set_my_commands(
                comandos_admin,
                scope=BotCommandScopeChat(chat_id=int(ADMIN_CHAT_ID)),
            )
        except Exception as e:
            logger.warning(f"Erro ao setar comandos admin: {e}")

    # Menu individual para cada admin da lista ADMIN_IDS
    for admin_id in ADMIN_IDS:
        try:
            await app.bot.set_my_commands(
                [
                    BotCommand("start", "Iniciar"),
                    BotCommand("admin", "Central Admin"),
                ],
                scope=BotCommandScopeChat(chat_id=admin_id),
            )
        except Exception as e:
            logger.warning(f"Não consegui setar menu para {admin_id}: {e}")

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN") or TELEGRAM_BOT_TOKEN
    app = (
        ApplicationBuilder()
        .token(token)
        .post_init(configurar_comandos)
        .build()
    )
    app.add_error_handler(erro_global_handler)

    # ConversationHandler - Atendimento Humanizado
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

    # ConversationHandler - Resposta do usuário ao chamado
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

    # ConversationHandler - Envio de mídia (admin)
        # ConversationHandler - Envio de mídia (admin)
    conv_envio_midia = ConversationHandler(
        entry_points=[
            CommandHandler("enviar_midia", iniciar_envio_midia),
            CommandHandler("enviar_imagem", iniciar_envio_midia),
            CommandHandler("enviar_documento", iniciar_envio_midia),
        ],
        states={
            AGUARDANDO_MIDIA_ADMIN: [
                MessageHandler(
                    filters.PHOTO | filters.Document.ALL | filters.VIDEO,
                    receber_midia_admin
                ),
            ],
            AGUARDANDO_DESTINO_ADMIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receber_destino_admin)
            ],
            AGUARDANDO_CONFIRMACAO_ENVIO: [
                CallbackQueryHandler(confirmar_envio_midia, pattern="^confirmar_envio_midia$"),
                CallbackQueryHandler(cancelar_envio_midia, pattern="^cancelar_envio_midia$"),
            ],
        },
        fallbacks=[
            CommandHandler("cancelar", cancelar_atendimento),
        ],
        per_message=False,
    )

    # Comandos principais
    app.add_handler(CommandHandler("start", comando_start))
    app.add_handler(CommandHandler("menu", menu_atendimento))
    app.add_handler(CommandHandler("faq", iniciar_faq))
    app.add_handler(CommandHandler("suporte", comando_suporte))
    app.add_handler(CommandHandler("chamados", comando_ver_chamados))
    app.add_handler(CommandHandler("responder", comando_responder_chamado))
    app.add_handler(CommandHandler("admin", menu_admin))

        # Conversation para responder chamado (admin)
    conv_resposta_admin = ConversationHandler(
        entry_points=[CallbackQueryHandler(
            callback_responder, pattern=r"^adm_responder_\d+$"
        )],
        states={
            AGUARDANDO_RESPOSTA_ADMIN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receber_resposta_admin)
            ],
        },
        fallbacks=[CommandHandler("cancelar_admin", cancelar_resposta_admin)],
        per_message=False,
    )

    # Conversation handlers
    app.add_handler(conv_resposta_admin)
    app.add_handler(conv_atendimento_humanizado)
    app.add_handler(conv_resposta_usuario)
    app.add_handler(conv_envio_midia)

    # Callbacks gerais
    app.add_handler(CallbackQueryHandler(menu_atendimento, pattern="^atendimento_menu$"))
    app.add_handler(CallbackQueryHandler(iniciar_faq, pattern="^atendimento_faq$"))
    app.add_handler(CallbackQueryHandler(ver_meus_chamados, pattern="^ver_chamados$"))
    app.add_handler(CallbackQueryHandler(callback_email_suporte, pattern="^atendimento_email$"))
    app.add_handler(CallbackQueryHandler(cancelar_atendimento, pattern="^cancelar_atendimento$"))
    app.add_handler(CallbackQueryHandler(menu_atendimento, pattern="^iniciar$"))
    app.add_handler(CallbackQueryHandler(sobre_vigia_saude, pattern="^sobre_vigia$"))
    app.add_handler(CallbackQueryHandler(callback_planos, pattern="^atendimento_planos$"))

    # Callbacks do FAQ
    app.add_handler(CallbackQueryHandler(faq_cadastrar, pattern="^faq_cadastrar$"))
    app.add_handler(CallbackQueryHandler(faq_consultar, pattern="^faq_consultar$"))
    app.add_handler(CallbackQueryHandler(faq_id, pattern="^faq_id$"))
    app.add_handler(CallbackQueryHandler(faq_alterar, pattern="^faq_alterar$"))
    app.add_handler(CallbackQueryHandler(faq_planos, pattern="^faq_planos$"))
    app.add_handler(CallbackQueryHandler(faq_governo, pattern="^faq_governo$"))

    # Central Admin VigiaSaúde
    app.add_handler(CallbackQueryHandler(
        callback_listar, pattern=r"^adm_(todos|aberto|em_atend)$"
    ))
    app.add_handler(CallbackQueryHandler(
        callback_estatisticas, pattern=r"^adm_stats$"
    ))
    app.add_handler(CallbackQueryHandler(
        callback_ver_chamado, pattern=r"^adm_ver_\d+$"
    ))
    app.add_handler(CallbackQueryHandler(
        callback_voltar, pattern=r"^adm_voltar$"
    ))
    app.add_handler(CallbackQueryHandler(
        callback_finalizar, pattern=r"^adm_finalizar_\d+$"
    ))
    app.add_handler(CallbackQueryHandler(
        callback_cancelar_resposta, pattern=r"^adm_cancelar_resp_\d+$"
    ))

    # Handler global para mensagens (IA automática)
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, processar_mensagem_geral),
        group=2,
    )

    # Servidor HTTP auxiliar para o Railway
    PORT = int(os.environ.get("PORT", "8080"))

    import threading
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class SimpleHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Central de Atendimento VigiaSaude is running!")

    def run_http_server(port):
        server = HTTPServer(("0.0.0.0", port), SimpleHandler)
        server.serve_forever()

    threading.Thread(target=run_http_server, args=(PORT,), daemon=True).start()
    logger.info(f"Servidor HTTP auxiliar rodando na porta {PORT}")

    logger.info("Iniciando a Central de Atendimento VigiaSaude via polling...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()