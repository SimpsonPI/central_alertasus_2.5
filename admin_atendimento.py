# admin_atendimento.py (na pasta Atendimento_VigiaSaude_bot)
# admin_atendimento.py
import logging
from telegram import Update
from telegram.ext import ContextTypes
from database_atendimento import supabase
from config import ADMIN_CHAT_ID

ADMIN_ID = ADMIN_CHAT_ID or 5242040324

logger = logging.getLogger(__name__)


async def comando_avaliacoes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Mostra média de satisfação dos chamados (apenas admin)."""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Acesso restrito a administradores.")
        return

    try:
        res = supabase.table("chamados_suporte").select("avaliacao").not_.is_("avaliacao", "null").execute()
        avaliacoes = [c["avaliacao"] for c in (res.data or []) if c.get("avaliacao")]

        if not avaliacoes:
            await update.message.reply_text("📊 Nenhuma avaliação recebida ainda.")
            return

        media = sum(avaliacoes) / len(avaliacoes)
        total = len(avaliacoes)
        positivas = len([a for a in avaliacoes if a >= 4])
        negativas = len([a for a in avaliacoes if a <= 2])
        neutras = total - positivas - negativas

        texto = (
            "📊 <b>RELATÓRIO DE SATISFAÇÃO</b>\n\n"
            f"⭐ <b>Média geral:</b> {media:.2f} / 5.00\n"
            f"📝 <b>Total de avaliações:</b> {total}\n\n"
            f"😄 Positivas (4-5): {positivas} ({positivas*100//total}%)\n"
            f"🙂 Neutras (3): {neutras}\n"
            f"😞 Negativas (1-2): {negativas} ({negativas*100//total}%)"
        )
        await update.message.reply_text(texto, parse_mode="HTML")
    except Exception as e:
        logger.error(f"Erro ao calcular avaliações: {e}")
        await update.message.reply_text("❌ Erro ao calcular avaliações.")