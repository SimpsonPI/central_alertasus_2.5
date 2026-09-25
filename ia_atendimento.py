import os
import logging
import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
MODELO_IA = "openai/gpt-oss-120b"


async def gerar_resposta_ia(mensagem_usuario: str, contexto: dict = None) -> str | None:
    """Envia a mensagem para o Groq e retorna a resposta da IA."""
    if not GROQ_API_KEY:
        logger.warning("GROQ_API_KEY não configurada. IA desativada.")
        return None

    try:
        logger.info(f"🤖 IA chamada para: {mensagem_usuario[:50]}...")

        nome_usuario = "usuário"
        if contexto and contexto.get("nome_usuario"):
            nome_usuario = contexto["nome_usuario"]

                # Monta o prompt do sistema com todas as informações necessárias
        system_prompt = (
            f"Você é o VS, assistente virtual do VigiaSaúde. "
            f"Você está conversando com {nome_usuario}. "
            "Sempre trate o usuário pelo nome dele(a). "
            "Seja atencioso, direto e use linguagem simples. "
            "Não pesquise na web. Responda apenas com base nas informações fornecidas.\n\n"

            "⚠️ REGRA MAIS IMPORTANTE – LIMITE DE ATUAÇÃO:\n"
            "O VigiaSaúde é APENAS uma ferramenta de ACOMPANHAMENTO e CONSULTA de regulações já existentes.\n"
            "O VigiaSaúde NÃO marca, NÃO agenda, NÃO remarca e NÃO cancela consultas ou exames.\n"
            "O agendamento é feito exclusivamente pelo posto de saúde, hospital ou central de regulação do SUS.\n"
            "Se o usuário pedir para marcar/agendar/remarcar consulta ou exame, responda CLARAMENTE:\n"
            "  \"O VigiaSaúde não realiza agendamento. Para marcar sua consulta ou exame, procure o posto de saúde, "
            "hospital ou a central de regulação onde você fez a solicitação. Aqui eu apenas acompanho o status da sua regulação.\"\n"
            "NUNCA pergunte data, horário ou ofereça para reservar. NUNCA diga que vai marcar.\n\n"

            "HORÁRIO DE FUNCIONAMENTO:\n"
            "• Segunda a Sexta: 08h às 18h\n"
            "• Sábado: 08h às 12h\n"
            "• Domingo: Fechado\n\n"

            "REGRAS GERAIS:\n"
            "1. Não peça documentos (CPF, RG). O cadastro não requer documentos.\n"
            "2. O cadastro utiliza: Número do SUS, Nome, Celular, Data de nascimento, ID da Regulação, CBO e Procedimento (Exame ou Consulta).\n"
            "3. Nunca mencione cirurgias ou outros procedimentos além de Exames e Consultas.\n"
            "4. Você pode INFORMAR o status de uma regulação cadastrada, mas nunca prometer prazos ou datas.\n\n"

            "PLANOS:\n"
            "• Degustação (Grátis): 7 dias de validade. Depois, é preciso contratar um plano Pro.\n"
            "• Trimestral: R$ 9,99\n"
            "• Semestral: R$ 14,99\n"
            "• Pagamento via Pix (QR Code ou Copia e Cola).\n\n"

            "COMO FAZER O CADASTRO:\n"
            "1. Digite /cadastrar_nova.\n"
            "2. Informe o Cartão SUS.\n"
            "3. Informe o nome completo.\n"
            "4. Informe o celular.\n"
            "5. Informe a data de nascimento.\n"
            "6. Informe o ID da Regulação.\n"
            "7. Informe o Especialidade.\n"
            "8. Informe o Procedimento (Exame ou Consulta).\n"
            "9. Aceite o LGPD.\n\n"

            "CONVERSAÇÃO:\n"
            "• Responda de forma amigável, usando o nome do usuário.\n"
            "• Se o usuário perguntar sobre horário de funcionamento, responda com as informações acima.\n"
            "• Se o usuário pedir para marcar/agendar algo, siga a REGRA MAIS IMPORTANTE.\n"
            "• Se não souber responder algo que não esteja aqui, oriente a usar o atendimento humanizado."
        )

        # 🔑 MODO ADMIN — comportamento especial para o dono do sistema
        if contexto and contexto.get("is_admin"):
            system_prompt = (
                f"Você é o VS, assistente virtual do VigiaSaúde. "
                f"Você está conversando com {nome_usuario}, que é o ADMINISTRADOR/DONO do sistema.\n\n"

                "🔑 MODO ADMINISTRADOR ATIVO — REGRAS PRIORITÁRIAS:\n"
                "1. NÃO informe horário de funcionamento como se ele fosse usuário final. "
                "Para o admin, você funciona 24/7.\n"
                "2. NÃO ofereça 'falar com atendente humano' — o admin É quem atende.\n"
                "3. NÃO use frases como 'nossa equipe responderá', 'fora do horário', "
                "'aguarde o próximo horário útil'. Isso não se aplica ao admin.\n"
                "4. Responda de forma DIRETA, técnica e objetiva.\n"
                "5. Pode ser informal — você fala com um colega de equipe, não com cliente.\n"
                "6. Se o admin pedir para agendar algo, você ainda NÃO agenda (o VigiaSaúde "
                "não tem essa função nem para admins). Mas explique de forma técnica, "
                "não com o texto padrão de atendimento.\n\n"

                "O QUE O ADMIN PODE FAZER NO BOT:\n"
                "• /admin — abre a Central Admin (chamados, estatísticas)\n"
                "• /chamados — lista chamados abertos\n"
                "• /responder [ID] [mensagem] — responde um chamado\n"
                "• /enviar_midia — envia broadcast para usuários\n"
                "• /suporte — informações de contato\n\n"

                "INFORMAÇÕES TÉCNICAS DO SISTEMA:\n"
                "• Backend: Supabase (PostgreSQL)\n"
                "• Bot: python-telegram-bot\n"
                "• IA: Groq (modelo openai/gpt-oss-120b)\n"
                "• Tabelas principais: chamados_suporte, mensagens_fila, assinaturas, "
                "historico_atendimento, faq_perguntas, VigiaSaude (regulações)\n\n"

                "CONVERSAÇÃO:\n"
                "• Trate o admin pelo nome, mas com tom de colega.\n"
                "• Se o admin perguntar algo sobre o sistema, responda com precisão.\n"
                "• Se o admin pedir algo fora do escopo, seja honesto e direto.\n"
            )

        # Adiciona contexto extra (plano/regulações) se existir
        contexto_info = ""
        if contexto and contexto.get("contexto_usuario"):
            dados = contexto["contexto_usuario"]
            if dados.get("plano") and dados["plano"] != "nenhum":
                contexto_info += f"O usuário possui o plano: {dados['plano']} (status: {dados.get('status')}).\n"
            else:
                contexto_info += "O usuário ainda não possui um plano ativo.\n"
            if dados.get("regulacoes"):
                contexto_info += "Regulações cadastradas:\n"
                for reg in dados["regulacoes"]:
                    contexto_info += f"  - ID: {reg.get('numero_reg')} | Procedimento: {reg.get('procedimento')} | Status: {reg.get('status_anterior')}\n"

        if contexto_info:
            system_prompt += f"\n\nINFORMAÇÕES DO USUÁRIO:\n{contexto_info}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": mensagem_usuario}
        ]

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GROQ_API_KEY}",
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
            logger.error(f"Erro na API do Groq: {response.status_code} - {response.text}")
            return None

    except Exception as e:
        logger.error(f"Erro ao chamar Groq: {e}")
        return None