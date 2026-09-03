import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

supabase = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

try:
    res = supabase.table("chamados_suporte").insert({
        "chat_id": "999999999",
        "nome_usuario": "Teste",
        "mensagem": "Teste de inserção"
    }).execute()
    print("✅ Inserção funcionou!")
except Exception as e:
    print(f"❌ ERRO COMPLETO: {repr(e)}")