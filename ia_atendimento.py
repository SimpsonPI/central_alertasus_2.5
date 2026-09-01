import os
import logging
import httpx

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# Modelo gratuito e automático
MODELO_IA = "openrouter/free"

import os
import logging
import httpx

logger = logging.getLogger(__name__)

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# Modelo gratuito e automático
MODELO_IA = "openrouter/free"

async def obter_conhecimento_github() -> str:
    """Busca o conteúdo do arquivo conhecimento.md no GitHub."""
    url = "https://raw.githubusercontent.com/SimpsonPI/central_alertasus_2.5/main/conhecimento.md"
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            if response.status_code == 200:
                return response.text
            else:
                logger.warning(f"Erro ao buscar conhecimento: {response.status_code}")
                return ""
    except Exception as e:
        logger.error(f"Erro ao buscar conhecimento: {e}")
        return ""


async def gerar_resposta_ia(mensagem_usuario: str, contexto: dict = None) -> str | None:
    """Envia a mensagem para o OpenRouter e retorna a resposta da IA, usando contexto do usuário e conhecimento do GitHub."""
    if not OPENROUTER_API_KEY:
        logger.warning("OPENROUTER_API_KEY não configurada. IA desativada.")
        return None

    try:
        # LOG PARA DIAGNÓSTICO
        logger.info(f"🤖 IA chamada para: {mensagem_usuario[:50]}...")

        # 1. Busca o conhecimento do GitHub (conhecimento.md)
        conhecimento = await obter_conhecimento_github()

        # 2. Estrutura o contexto do usuário para o prompt
        contexto_info = ""
        if contexto and contexto.get("contexto_usuario"):
            dados = contexto["contexto_usuario"]

            # Informações do plano
            if dados.get("plano") and dados["plano"] != "nenhum":
                contexto_info += f"O usuário possui o plano: {dados['plano']} (status: {dados.get('status')}).\n"
                if dados.get("data_vencimento"):
                    contexto_info += f"Vencimento do plano: {dados['data_vencimento']}.\n"
            else:
                contexto_info += "O usuário ainda não possui um plano ativo.\n"

            if dados.get("usou_degustacao"):
                contexto_info += "O usuário já utilizou o período de degustação.\n"

            # Informações das regulações
            if dados.get("regulacoes"):
                contexto_info += "Regulações cadastradas:\n"
                for reg in dados["regulacoes"]:
                    contexto_info += f"  - ID: {reg.get('numero_reg')} | Procedimento: {reg.get('procedimento')} | Status: {reg.get('status_anterior')}\n"
            else:
                contexto_info += "O usuário não possui regulações cadastradas.\n"

        # 3. Monta o prompt do sistema com o conhecimento + contexto
        system_prompt = (
            "Você é o assistente virtual do AlertaSUS 2.0. Use SOMENTE as informações abaixo para responder.\n\n"
            f"{conhecimento}\n\n"
            "REGRAS:\n"
            "1. Não invente informações.\n"
            "2. Não pesquise na web.\n"
            "3. Se não souber, oriente o usuário a usar o atendimento humanizado.\n"
        )

        # Adiciona o contexto do usuário ao prompt (se houver)
        if contexto_info:
            system_prompt += f"\n\nINFORMAÇÕES DO USUÁRIO:\n{contexto_info}"

        messages = [{"role": "system", "content": system_prompt}]
        if contexto and contexto.get("nome_usuario"):
            messages.append({"role": "system", "content": f"O usuário se chama {contexto['nome_usuario']}."})
        messages.append({"role": "user", "content": mensagem_usuario})

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": MODELO_IA,
                    "messages": messages,
                    "stream": False
                }
            )

        if response.status_code == 200:
            data = response.json()
            resposta = data["choices"][0]["message"]["content"]
            logger.info(f"🤖 IA respondeu: {resposta[:50]}...")
            return resposta.strip()
        else:
            logger.error(f"Erro na API do OpenRouter: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        logger.error(f"Erro ao chamar OpenRouter: {e}")
        return None
        # SISTEMA PROMPT - CONTROLE TOTAL DO COMPORTAMENTO DA IA
        system_prompt = (
            "Você é o assistente virtual oficial do AlertaSUS 2.0, um serviço independente "
            "que monitora regulações de saúde (consultas e exames) no SUS de Teresina-PI.\n\n"

            "REGRAS IMPORTANTES:\n"
            "1. NÃO pesquise na web. Responda APENAS com base nas informações deste prompt.\n"
            "2. NÃO peça documentos (CPF, RG, anexos). O cadastro NÃO requer documentos.\n"
            "3. O cadastro utiliza apenas: Número do SUS, Nome completo, Celular, Data de nascimento, "
            "ID da Regulação, CBO/Especialidade e Procedimento (Exame ou Consulta).\n"
            "4. NÃO mencione cirurgias ou outros tipos de procedimentos além de Exames e Consultas.\n\n"

            "PLANOS E ASSINATURAS:\n"
            "• Plano Degustação (Grátis): Tem validade de 7 dias. Após esse período, o usuário deve "
            "contratar um dos planos Pro para continuar monitorando.\n"
            "• Planos Pro disponíveis:\n"
            "   - Trimestral (R$ 9,99)\n"
            "   - Semestral (R$ 14,99)\n"
            "• Para assinar, o usuário acessa /planos e paga via Pix.\n\n"

            "COMO FAZER O CADASTRO (PASSO A PASSO):\n"
            "1. Digite /cadastrar_nova no chat.\n"
            "2. Informe o número do Cartão SUS (15 dígitos).\n"
            "3. Informe o nome completo do paciente.\n"
            "4. Informe o celular com DDD.\n"
            "5. Informe a data de nascimento (DD/MM/AAAA).\n"
            "6. Informe o ID da Regulação (número).\n"
            "7. Informe o CBO/Especialidade.\n"
            "8. Informe o Procedimento (Exame ou Consulta).\n"
            "9. Aceite o Termo de Consentimento LGPD.\n"
            "Pronto! A regulação será monitorada automaticamente.\n\n"

            "EXEMPLOS DE RESPOSTA:\n"
            "• Se perguntarem sobre cadastro, explique o passo a passo acima.\n"
            "• Se perguntarem sobre a degustação, diga que são 7 dias grátis e depois é preciso contratar um plano Pro.\n"
            "• Se perguntarem sobre documentos, diga que NÃO é necessário anexar nada.\n\n"

            "CONVERSAÇÃO:\n"
            "• Responda de forma amigável e objetiva.\n"
            "• Se não souber responder, oriente a usar o atendimento humanizado."
        )

        # Adiciona as informações do usuário ao prompt do sistema
        if contexto_info:
            system_prompt += (
                "\n\nINFORMAÇÕES DO USUÁRIO (dados reais do sistema):\n"
                f"{contexto_info}"
                "Use essas informações para personalizar sua resposta."
            )

        messages = [{"role": "system", "content": system_prompt}]
        if contexto and contexto.get("nome_usuario"):
            messages.append({"role": "system", "content": f"O usuário se chama {contexto['nome_usuario']}."})
        messages.append({"role": "user", "content": mensagem_usuario})

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": MODELO_IA,
                    "messages": messages,
                    "stream": False
                }
            )

        if response.status_code == 200:
            data = response.json()
            resposta = data["choices"][0]["message"]["content"]
            logger.info(f"🤖 IA respondeu: {resposta[:50]}...")
            return resposta.strip()
        else:
            logger.error(f"Erro na API do OpenRouter: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        logger.error(f"Erro ao chamar OpenRouter: {e}")
        return None
