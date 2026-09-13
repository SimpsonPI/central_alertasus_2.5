# database_atendimento.py
import os
import logging
from datetime import datetime, timezone
from supabase import create_client, Client

logger = logging.getLogger(__name__)

# Conexão direta com o Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("As variáveis SUPABASE_URL e SUPABASE_KEY precisam estar configuradas no .env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==========================================
# FUNÇÃO PARA BUSCAR CONTEXTO DO USUÁRIO
# ==========================================

async def buscar_contexto_usuario(chat_id: str) -> dict:
    """Busca informações do usuário no Supabase para fornecer contexto à IA."""
    contexto = {}
    try:
        # Busca dados da assinatura
        res_assinatura = supabase.table("assinaturas").select("*").eq("chat_id", str(chat_id)).execute()
        if res_assinatura.data:
            assinatura = res_assinatura.data[0]
            contexto["plano"] = assinatura.get("tipo_plano")
            contexto["status"] = assinatura.get("status")
            contexto["data_vencimento"] = assinatura.get("data_vencimento")
            contexto["limite_ids"] = assinatura.get("limite_ids")
            contexto["usou_degustacao"] = assinatura.get("usou_degustacao", False)
        else:
            contexto["plano"] = "nenhum"
            contexto["status"] = "novo"
            contexto["usou_degustacao"] = False

        # Busca regulações cadastradas
        res_regulacoes = supabase.table("AlertaSUS_2.0").select("numero_reg, procedimento, status_anterior").eq("chat_id", str(chat_id)).execute()
        if res_regulacoes.data:
            contexto["regulacoes"] = res_regulacoes.data
        else:
            contexto["regulacoes"] = []

        return contexto
    except Exception as e:
        logger.error(f"Erro ao buscar contexto do usuário {chat_id}: {e}")
        return contexto

# ==========================================
# FUNÇÕES PARA FAQ AUTOMATIZADO
# ==========================================

async def buscar_faq_por_palavras_chave(texto_usuario: str) -> dict | None:
    """Busca no banco de dados uma resposta do FAQ baseada nas palavras-chave."""
    try:
        texto_normalizado = texto_usuario.lower().strip()
        
        res = supabase.table("faq_perguntas").select("*").eq("ativo", True).execute()
        
        if not res.data:
            return None
        
        melhor_match = None
        melhor_pontuacao = 0
        
        for faq in res.data:
            pontuacao = 0
            palavras_chave = faq.get("palavras_chave", [])
            
            for palavra in palavras_chave:
                if palavra.lower() in texto_normalizado:
                    pontuacao += 1
            
            if faq.get("pergunta", "").lower() in texto_normalizado:
                pontuacao += 3
            
            if pontuacao > melhor_pontuacao:
                melhor_pontuacao = pontuacao
                melhor_match = faq
        
        if melhor_match and melhor_pontuacao > 0:
            return melhor_match
        
        return None
        
    except Exception as e:
        logger.error(f"Erro ao buscar FAQ: {e}")
        return None


# ==========================================
# FUNÇÕES PARA ATENDIMENTO HUMANIZADO
# ==========================================

async def registrar_chamado_suporte(chat_id: str, nome_usuario: str, mensagem: str) -> int | None:
    """Registra um novo chamado de suporte humanizado."""
    try:
        res = supabase.table("chamados_suporte").insert({
            "chat_id": str(chat_id),
            "nome_usuario": nome_usuario,
            "mensagem": mensagem,
        }).execute()

        if res.data:
            return res.data[0]["id"]
        return None

    except Exception as e:
        logger.error(f"ERRO COMPLETO: {repr(e)}")  # Mostra o erro real do Supabase
        logger.error(f"DETALHES: {e}")
        return None
        
async def adicionar_mensagem_fila(chamado_id: int, chat_id: str, mensagem: str, enviado_por: str = "usuario") -> bool:
    """Adiciona uma mensagem à fila do chamado."""
    try:
        supabase.table("mensagens_fila").insert({
            "chamado_id": chamado_id,
            "chat_id": str(chat_id),
            "mensagem": mensagem,
            "enviado_por": enviado_por
        }).execute()
        
        return True
        
    except Exception as e:
        logger.error(f"Erro ao adicionar mensagem à fila: {e}")
        return False


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


async def registrar_historico(chat_id: str, tipo: str, mensagem: str, origem: str = "bot") -> bool:
    """Registra uma mensagem no histórico de atendimento."""
    try:
        supabase.table("historico_atendimento").insert({
            "chat_id": str(chat_id),
            "tipo": tipo,
            "mensagem": mensagem,
            "origem": origem
        }).execute()
        
        return True
        
    except Exception as e:
        logger.error(f"Erro ao registrar histórico: {e}")
        return False


# ==========================================
# FUNÇÕES DE CONFIGURAÇÃO
# ==========================================

async def obter_configuracao(chave: str) -> str | None:
    """Obtém uma configuração do sistema."""
    try:
        res = supabase.table("configuracoes_atendimento").select("valor").eq("chave", chave).execute()
        
        if res.data:
            return res.data[0]["valor"]
        return None
        
    except Exception as e:
        logger.error(f"Erro ao obter configuração {chave}: {e}")
        return None


async def obter_email_suporte() -> str:
    """Obtém o email de suporte configurado."""
    email = await obter_configuracao("email_suporte")
    return email or "suportevigiasaude@gmail.com"

async def buscar_estatisticas_admin() -> dict:
    """Busca estatísticas do sistema para o administrador."""
    stats = {
        "total_usuarios": 0,
        "total_chamados_abertos": 0,
        "total_assinaturas_ativas": 0,
        "total_regulacoes": 0,
        "ultimos_chamados": []
    }

    # 1. Total de usuários únicos (chat_id distintos em assinaturas)
        # 1. Total de usuários únicos (chat_id distintos em assinaturas)
    try:
        res = supabase.table("assinaturas").select("chat_id").execute()
        logger.info(f"📊 Retorno assinaturas: {res.data}")
        if res.data:
            chat_ids_unicos = set(str(row["chat_id"]) for row in res.data if row.get("chat_id"))
            stats["total_usuarios"] = len(chat_ids_unicos)
            logger.info(f"📊 Usuários únicos: {stats['total_usuarios']}")
        else:
            logger.warning("📊 Retorno vazio da tabela assinaturas (RLS pode estar bloqueando)")
    except Exception as e:
        logger.error(f"❌ Erro ao contar usuários: {repr(e)}")

    # 2. Chamados abertos
    try:
        res = supabase.table("chamados_suporte").select("id").in_("status", ["aberto", "em_andamento"]).execute()
        stats["total_chamados_abertos"] = len(res.data) if res.data else 0
        logger.info(f"📊 Chamados abertos: {stats['total_chamados_abertos']}")
    except Exception as e:
        logger.error(f"❌ Erro ao contar chamados abertos: {repr(e)}")

    # 3. Assinaturas ativas
    try:
        res = supabase.table("assinaturas").select("chat_id, status").execute()
        logger.info(f"📊 Amostra de assinaturas: {res.data[:3] if res.data else 'vazio'}")
        if res.data:
            ativas = [a for a in res.data if str(a.get("status", "")).lower() in ("ativo", "active", "ativa")]
            stats["total_assinaturas_ativas"] = len(ativas)
            logger.info(f"📊 Assinaturas ativas: {stats['total_assinaturas_ativas']}")
    except Exception as e:
        logger.error(f"❌ Erro ao contar assinaturas: {repr(e)}")

    # 4. Total de regulações
    try:
        res = supabase.table("AlertaSUS_2.0").select("numero_reg").execute()
        stats["total_regulacoes"] = len(res.data) if res.data else 0
        logger.info(f"📊 Total de regulações: {stats['total_regulacoes']}")
    except Exception as e:
        logger.error(f"❌ Erro ao contar regulações: {repr(e)}")

    # 5. Últimos 5 chamados
    try:
        res = supabase.table("chamados_suporte").select("id, nome_usuario, status").order("created_at", desc=True).limit(5).execute()
        stats["ultimos_chamados"] = res.data if res.data else []
        logger.info(f"📊 Últimos chamados: {len(stats['ultimos_chamados'])}")
    except Exception as e:
        logger.error(f"❌ Erro ao buscar últimos chamados: {repr(e)}")

    # Debug final
    logger.info(f"📊 ESTATÍSTICAS FINAIS: {stats}")

    return stats