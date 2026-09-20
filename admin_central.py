from dotenv import load_dotenv
load_dotenv()

from datetime import datetime, timezone
from database_atendimento import (
    listar_chamados_abertos,
    supabase,
)

STATUS_EMOJI = {
    "aberto": "🟢",
    "em_andamento": "🔵",
    "aguardando_usuario": "🟡",
    "respondido": "✅",
    "fechado": "⚪",
}

PRIORIDADE_EMOJI = {
    "baixa": "🔽",
    "normal": "➖",
    "alta": "🔼",
    "urgente": "🚨",
}


def _tempo_relativo(iso_str: str) -> str:
    """Converte timestamp ISO em '2h atrás', '3d atrás' etc."""
    if not iso_str:
        return "?"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
    except ValueError:
        return "?"
    agora = datetime.now(timezone.utc)
    delta = agora - dt
    if delta.days > 0:
        return f"{delta.days}d atrás"
    if delta.seconds >= 3600:
        return f"{delta.seconds // 3600}h atrás"
    if delta.seconds >= 60:
        return f"{delta.seconds // 60}min atrás"
    return "agora"


async def obter_chamados_pendentes(status_filtro: str | None = None) -> list[dict]:
    """
    Retorna chamados pendentes.
    status_filtro: None (todos), 'aberto', 'em_andamento', etc.
    """
    chamados = await listar_chamados_abertos()

    if status_filtro:
        chamados = [c for c in chamados if c.get("status") == status_filtro]

    # Ordena: prioridade urgente primeiro, depois mais antigos
    ordem_prioridade = {"urgente": 0, "alta": 1, "normal": 2, "baixa": 3}
    chamados.sort(key=lambda c: (
        ordem_prioridade.get(c.get("prioridade", "normal"), 2),
        c.get("created_at", "")
    ))
    return chamados


def formatar_lista_chamados(chamados: list[dict], max_itens: int = 20) -> str:
    """Formata a lista para o Telegram (Markdown)."""
    if not chamados:
        return "📭 *Nenhum chamado pendente no momento.*"

    linhas = [f"📋 *CHAMADOS PENDENTES* ({len(chamados)})\n"]

    for ch in chamados[:max_itens]:
        emoji = STATUS_EMOJI.get(ch.get("status"), "❔")
        prio = PRIORIDADE_EMOJI.get(ch.get("prioridade", "normal"), "➖")
        tempo = _tempo_relativo(ch.get("created_at"))
        nome = ch.get("nome_usuario") or ch.get("chat_id")

        # Prévia da mensagem
        msg = (ch.get("mensagem") or "").replace("\n", " ")
        previa = (msg[:50] + "…") if len(msg) > 50 else msg

        linhas.append(
            f"{emoji} *#{ch['id']}* {prio} — {nome}\n"
            f"   💬 {previa}\n"
            f"   ⏱️ {tempo} • status: `{ch.get('status')}`\n"
        )

    if len(chamados) > max_itens:
        linhas.append(f"\n_…e mais {len(chamados) - max_itens} chamados._")

    return "\n".join(linhas)


async def estatisticas_chamados() -> dict:
    """Retorna contagem por status."""
    chamados = await listar_chamados_abertos()
    stats = {"aberto": 0, "em_andamento": 0, "respondido": 0, "outros": 0}
    for c in chamados:
        s = c.get("status", "outros")
        if s in stats:
            stats[s] += 1
        else:
            stats["outros"] += 1
    stats["total"] = len(chamados)
    return stats


def formatar_estatisticas(stats: dict) -> str:
    return (
        "📊 *ESTATÍSTICAS DE CHAMADOS*\n\n"
        f"🟢 Abertos: *{stats['aberto']}*\n"
        f"🔵 Em andamento: *{stats['em_andamento']}*\n"
        f"✅ Respondidos: *{stats['respondido']}*\n"
        f"⚪ Outros: *{stats['outros']}*\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📌 Total: *{stats['total']}*"
    )