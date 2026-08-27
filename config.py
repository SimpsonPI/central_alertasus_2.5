import os
from dotenv import load_dotenv
load_dotenv()

BOT_PUBLICO_TOKEN = os.getenv("BOT_PUBLICO_TOKEN")
BOT_ATENDIMENTO_TOKEN = os.getenv("BOT_ATENDIMENTO_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
MERCADO_PAGO_ACCESS_TOKEN = os.getenv("MERCADO_PAGO_ACCESS_TOKEN")

# === ADICIONE ESTA PARTE NO FINAL DE config.py ===
erros = []
if not BOT_PUBLICO_TOKEN: erros.append("BOT_PUBLICO_TOKEN está VAZIO")
if not BOT_ATENDIMENTO_TOKEN: erros.append("BOT_ATENDIMENTO_TOKEN está VAZIO")
if not SUPABASE_URL: erros.append("SUPABASE_URL está VAZIO")
if not SUPABASE_KEY: erros.append("SUPABASE_KEY está VAZIO")

if erros:
    print("❌ ERROS encontrados no .env:")
    for e in erros: print(f"   - {e}")
    exit(1)

print("✅ Todas as variáveis carregadas com sucesso!")