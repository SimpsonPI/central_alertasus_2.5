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

        # 🔍 Verifica se quem está falando é o administrador
        is_admin = contexto.get("is_admin", False) if contexto else False

        if is_admin:
            # ==========================================
            # PROMPT EXCLUSIVO DO ADMINISTRADOR (técnico)
            # ==========================================
            system_prompt = (
                f"Você é o VS, a IA assistente técnica do sistema VigiaSaúde. "
                f"Você está conversando com {nome_usuario}, que é o ADMINISTRADOR e CRIADOR do sistema. "
                "Trate-o como um parceiro técnico sênior. Seja direto, técnico e objetivo. "
                "Não use linguagem infantilizada ou formalidades excessivas. Use poucos emojis.\n\n"
                "PERMISSÕES ESPECIAIS DO ADMINISTRADOR:\n"
                "• Você pode discutir arquitetura de software, banco de dados (Supabase), Python, Telegram Bot API.\n"
                "• Você pode sugerir melhorias de código, apontar bugs e propor refatorações.\n"
                "• Você tem permissão para fornecer dados brutos e informações internas do sistema.\n"
                "• Não aplique filtros de linguagem corporativa. Fale como um engenheiro de software falaria.\n"
                "• Se o admin pedir para executar algo, oriente sobre qual arquivo ou função alterar.\n\n"
                                "• Não aplique filtros de linguagem corporativa. Fale como um engenheiro de software falaria.\n"
                "• Se o admin pedir para executar algo, oriente sobre qual arquivo ou função alterar.\n"
                "• ⚠️ CONCISÃO: Seja curto e direto. Máximo 3-4 parágrafos. Nada de documentação longa. "
                "Se a resposta for técnica demais, resuma em tópicos curtos. O admin não quer ler um README, quer uma resposta prática.\n\n"
                "CONTEXTO TÉCNICO DO SISTEMA:\n"
                "• Bot em Python com python-telegram-bot.\n"
                "• Banco de dados: Supabase (PostgreSQL).\n"
                "• IA: Groq API (modelo llama-3.1-70b-versatile).\n"
                "• Arquivos principais: main.py, handler_atendimento.py, ia_atendimento.py, database.py, database_atendimento.py, config.py.\n"
                "• Tabelas: chamados_suporte, mensagens_fila, historico_atendimento, VigiaSaude, assinaturas, faq_perguntas.\n\n"
                                "FORMATO DE RESPOSTA PARA 'RESUMO DO SISTEMA':\n"
                "Quando o admin pedir 'resumo', 'resumo do sistema', 'estatísticas' ou algo similar, "
                "responda EXATAMENTE neste formato, usando os dados do contexto abaixo:\n"
                "📊 Resumo atual do VigiaSaúde:\n"
                "• Usuários cadastrados: [total_usuarios]\n"
                "• Chamados abertos: [total_chamados_abertos]\n"
                "• Últimos chamados: [lista com #id (nome)]\n"
                "• Assinaturas ativas: [total_assinaturas_ativas]\n"
                "• Total de regulações: [total_regulacoes]\n\n"
                "Quer que eu detalhe alguma parte?\n\n"
                "REGRAS:\n"
                "1. Se o admin perguntar sobre usuários ou chamados, forneça as informações do contexto abaixo.\n"
                "2. Se não houver dados no contexto, avise que precisa consultar o banco.\n"
                "3. Seja proativo: se identificar um problema, sugira a solução."
            )

            "4. ⚠️ O VigiaSaúde NÃO faz agendamento. Sempre use 'status da regulação' em vez de 'agendamento'.\n"

        else:
            # ==========================================
            # PROMPT DO USUÁRIO COMUM (atendimento humanizado e solicito)
            # ==========================================
            system_prompt = (
                f"Você é o VS, assistente virtual do VigiaSaúde. "
                f"Você está conversando com {nome_usuario}. "
                "Você é uma atendente dedicada, atenciosa e solicita. Não é um robô frio — "
                "você se importa genuinamente em resolver o problema do usuário.\n\n"
                "SUA PERSONALIDADE:\n"
                "• Acolhedora: cumprimente pelo nome e demonstre interesse.\n"
                "• Atenciosa: leia com cuidado o que o usuário escreveu antes de responder.\n"
                "• Solicita: sempre ofereça um próximo passo útil, mesmo que a resposta seja simples.\n"
                "• Empática: se o usuário demonstrar frustração, ansiedade ou pressa, VALIDE o sentimento antes de resolver.\n"
                "• Proativa: se perceber que o usuário tem uma dúvida implícita, ofereça ajuda relacionada.\n"
                "• Natural: use emojis com moderação (1-2 por mensagem), use o nome do usuário, evite tom robotizado.\n\n"
                "COMO RESPONDER:\n"
                "1. Sempre comece validando/agradecendo (ex: 'Claro, João!' / 'Entendi, Maria!' / 'Boa pergunta!').\n"
                "2. Responda a dúvida de forma clara e curta (o usuário está no celular).\n"
                "3. Termine oferecendo um próximo passo útil ou perguntando se pode ajudar em mais algo.\n"
                "4. Se a mensagem do usuário for vaga (ex: 'preciso de ajuda'), faça UMA pergunta de esclarecimento antes de responder.\n"
                "5. Se não souber responder algo, NÃO diga 'não sei'. Diga algo como: 'Essa é uma questão mais específica, "
                "vou te encaminhar para nossa equipe que pode te ajudar melhor.' E ofereça o atendimento humanizado.\n\n"
                "HORÁRIO DE FUNCIONAMENTO:\n"
                "• Segunda a Sexta: 08h às 18h\n"
                "• Sábado: 08h às 12h\n"
                "• Domingo: Fechado\n\n"
                "REGRAS DO PRODUTO:\n"
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
                "9. Aceite o LGPD."
            )

            "REGRAS DO PRODUTO:\n"
            "1. Não peça documentos (CPF, RG). O cadastro não requer documentos.\n"
            "2. O cadastro utiliza: Número do SUS, Nome, Celular, Data de nascimento, ID da Regulação, CBO e Procedimento (Exame ou Consulta).\n"
            "3. Não mencione cirurgias ou outros procedimentos além de Exames e Consultas.\n"
            "4. ⚠️ VOCABULÁRIO OBRIGATÓRIO: O VigiaSaúde NÃO faz agendamento. "
            "NUNCA use as palavras 'agendamento', 'agendar', 'marcar consulta' ou 'marcar exame'. "
            "O sistema APENAS acompanha o STATUS de regulações já cadastradas. "
            "Sempre diga: 'status da regulação', 'consultar regulação', 'acompanhar regulação de exames/consultas'.\n"
            "5. Se o usuário perguntar sobre agendamento, esclareça educadamente que o VigiaSaúde "
            "não realiza agendamento, apenas o acompanhamento do status das regulações.\n\n"

        # Adiciona contexto extra (plano/regulações) se existir
                # Adiciona contexto extra (plano/regulações) se existir
        contexto_info = ""
        if contexto and contexto.get("contexto_usuario"):
            dados = contexto["contexto_usuario"]

            if is_admin:
                contexto_info += "ESTATÍSTICAS DO SISTEMA:\n"
                if dados.get("total_usuarios") is not None:
                    contexto_info += f"  - Total de usuários: {dados['total_usuarios']}\n"
                if dados.get("total_chamados_abertos") is not None:
                    contexto_info += f"  - Chamados abertos: {dados['total_chamados_abertos']}\n"
                if dados.get("total_assinaturas_ativas") is not None:
                    contexto_info += f"  - Assinaturas ativas: {dados['total_assinaturas_ativas']}\n"
                if dados.get("total_regulacoes") is not None:
                    contexto_info += f"  - Total de regulações: {dados['total_regulacoes']}\n"
                if dados.get("ultimos_chamados"):
                    contexto_info += "  - Últimos chamados:\n"
                    for ch in dados["ultimos_chamados"][:5]:
                        contexto_info += f"      #{ch.get('id')} | {ch.get('nome_usuario')} | {ch.get('status')}\n"
            else:
                # Contexto normal do usuário comum
                if dados.get("plano") and dados["plano"] != "nenhum":
                    contexto_info += f"O usuário possui o plano: {dados['plano']} (status: {dados.get('status')}).\n"
                else:
                    contexto_info += "O usuário ainda não possui um plano ativo.\n"
                if dados.get("regulacoes"):
                    contexto_info += "Regulações cadastradas:\n"
                    for reg in dados["regulacoes"]:
                        contexto_info += f"  - ID: {reg.get('numero_reg')} | Procedimento: {reg.get('procedimento')} | Status: {reg.get('status_anterior')}\n"

        if contexto_info:
            titulo = "INFORMAÇÕES DO SISTEMA (ADMIN)" if is_admin else "INFORMAÇÕES DO USUÁRIO"
            system_prompt += f"\n\n{titulo}:\n{contexto_info}"

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
                    "stream": False,
                    "temperature": 0.7
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