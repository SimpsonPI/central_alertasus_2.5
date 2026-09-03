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
            "HORÁRIO DE FUNCIONAMENTO:\n"
            "• Segunda a Sexta: 08h às 18h\n"
            "• Sábado: 08h às 12h\n"
            "• Domingo: Fechado\n\n"
            "REGRAS:\n"
            "1. Não peça documentos (CPF, RG). O cadastro não requer documentos.\n"
            "2. O cadastro utiliza: Número do SUS, Nome, Celular, Data de nascimento, ID da Regulação, CBO e Procedimento (Exame ou Consulta).\n"
            "3. Não mencione cirurgias ou outros procedimentos além de Exames e Consultas.\n\n"
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
            "7. Informe o CBO.\n"
            "8. Informe o Procedimento (Exame ou Consulta).\n"
            "9. Aceite o LGPD.\n\n"
            "CONVERSAÇÃO:\n"
            "• Responda de forma amigável, usando o nome do usuário.\n"
            "• Se o usuário perguntar sobre horário de funcionamento, responda com as informações acima.\n"
            "• Se não souber responder algo que não esteja aqui, oriente a usar o atendimento humanizado."
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