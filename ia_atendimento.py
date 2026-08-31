# ia_atendimento.py
import os
import logging
import asyncio
from openrouter import OpenRouter

logger = logging.getLogger(__name__)

# Obtém a chave da API do ambiente
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")

# Modelo a ser usado (você pode trocar por outro disponível no OpenRouter)
MODELO_IA = "google/gemini-3.1-flash-lite"  # Modelo leve e rápido (gratuito ou barato)

async def gerar_resposta_ia(mensagem_usuario: str, contexto: dict = None) -> str | None:
    """
    Envia a mensagem do usuário para o OpenRouter e retorna a resposta gerada pela IA.
    Retorna None se a chave da API não estiver configurada ou se houver erro.
    """
    if not OPENROUTER_API_KEY:
        logger.warning("OPENROUTER_API_KEY não configurada. IA desativada.")
        return None

    try:
        # Monta o contexto do sistema com informações do AlertaSUS
        system_prompt = (
            "Você é o assistente virtual do AlertaSUS 2.0, um serviço independente que monitora "
            "regulações de saúde (consultas, exames e cirurgias) no sistema SUS de Teresina-PI.\n\n"
            "Você pode ajudar com:\n"
            "- Como cadastrar uma nova regulação (use o comando /cadastrar_nova)\n"
            "- Como verificar o status das regulações (use /verificar_todos)\n"
            "- Como corrigir dados (use /corrigir)\n"
            "- Informações sobre planos (use /planos)\n"
            "- Dúvidas sobre o funcionamento do serviço\n\n"
            "Seja sempre claro, educado e objetivo. Se a pergunta for sobre algo que você não sabe, "
            "oriente o usuário a utilizar o atendimento humanizado."
        )

        # Prepara as mensagens para a API
        messages = [{"role": "system", "content": system_prompt}]
        
        # Adiciona contexto adicional se fornecido (ex: nome do usuário)
        if contexto and contexto.get("nome_usuario"):
            messages.append({"role": "system", "content": f"O usuário se chama {contexto['nome_usuario']}."})
        
        messages.append({"role": "user", "content": mensagem_usuario})

        # Usa o SDK do OpenRouter (síncrono, mas chamado em thread para não bloquear)
        def chamar_api():
            with OpenRouter(api_key=OPENROUTER_API_KEY) as client:
                response = client.chat.send(
                    model=MODELO_IA,
                    messages=messages,
                    stream=False
                )
                return response.choices[0].message.content

        # Executa a chamada em thread separada para não bloquear o bot
        resposta = await asyncio.to_thread(chamar_api)
        return resposta.strip()

    except Exception as e:
        logger.error(f"Erro ao chamar OpenRouter: {e}")
        return None