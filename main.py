import os
import logging
from telegram import BotCommand, BotCommandScopeAllPrivateChats
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from handler_atendimento import (
    menu_atendimento,
    iniciar_faq,
    processar_pergunta_faq,
    iniciar_atendimento_humanizado,
    processar_mensagem_humanizado,
    ver_meus_chamados,
    comando_ver_chamados,
    comando_responder_chamado,
    cancelar_atendimento,
    callback_email_suporte,  # <-- ADICIONE ESTA LINHA
    AGUARDANDO_MENSAGEM_CHAMADO,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

async def erro_global_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(msg="Exceção capturada pelo bot:", exc_info=context.error)

def main():
    token = os.getenv("TELEGRAM_BOT_TOKEN") or TELEGRAM_BOT_TOKEN
    app = ApplicationBuilder().token(token).build()
    app.add_error_handler(erro_global_handler)

    # ConversationHandler para Atendimento Humanizado
    conv_atendimento_humanizado = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(iniciar_atendimento_humanizado, pattern="^atendimento_humanizado$"),
            CommandHandler("atendimento_humanizado", iniciar_atendimento_humanizado),
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

    # Comandos principais
    app.add_handler(CommandHandler("start", menu_atendimento))
    app.add_handler(CommandHandler("menu", menu_atendimento))
    app.add_handler(CommandHandler("atendimento", menu_atendimento))
    app.add_handler(CommandHandler("faq", iniciar_faq))
    app.add_handler(CommandHandler("chamados", comando_ver_chamados))
    app.add_handler(CommandHandler("responder", comando_responder_chamado))

    # ConversationHandler
    app.add_handler(conv_atendimento_humanizado)

    # Callbacks
    app.add_handler(CallbackQueryHandler(menu_atendimento, pattern="^atendimento_menu$"))
    app.add_handler(CallbackQueryHandler(iniciar_faq, pattern="^atendimento_faq$"))
    app.add_handler(CallbackQueryHandler(iniciar_atendimento_humanizado, pattern="^atendimento_humanizado$"))
    app.add_handler(CallbackQueryHandler(ver_meus_chamados, pattern="^ver_chamados$"))
    app.add_handler(CallbackQueryHandler(cancelar_atendimento, pattern="^cancelar_atendimento$"))
    app.add_handler(CallbackQueryHandler(callback_email_suporte, pattern="^atendimento_email$"))

    # Handler para processar perguntas do FAQ quando o usuário digita texto
    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, processar_pergunta_faq),
        group=1
    )

    # Servidor HTTP auxiliar para o Railway manter a porta aberta
    PORT = int(os.environ.get("PORT", "8080"))
    
    import threading
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class SimpleHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"Central de Atendimento AlertaSUS is running!")

    def run_http_server(port):
        server = HTTPServer(("0.0.0.0", port), SimpleHandler)
        server.serve_forever()

    threading.Thread(target=run_http_server, args=(PORT,), daemon=True).start()
    logger.info(f"Servidor HTTP auxiliar rodando na porta {PORT}")

    logger.info("Iniciando a Central de Atendimento AlertaSUS via polling...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()