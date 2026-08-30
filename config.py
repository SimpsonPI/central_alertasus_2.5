import os
from dotenv import load_dotenv
from supabase import create_client, Client

# Carrega estritamente o arquivo .env
load_dotenv()

# Variáveis de Ambiente
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# IDs de Administração
raw_admin_id = os.getenv("ADMIN_CHAT_ID", "5242040324").strip()
ADMIN_CHAT_ID = int(raw_admin_id) if raw_admin_id.isdigit() else None

raw_admin_ids = os.getenv("ADMIN_IDS", "5242040324").strip()
ADMIN_IDS = [int(x.strip()) for x in raw_admin_ids.split(",") if x.strip().isdigit()]

PORT = int(os.getenv("PORT", 8080))

# Validação das variáveis obrigatórias
if not TELEGRAM_BOT_TOKEN or not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("⚠️ ERRO CRÍTICO: Variáveis TELEGRAM_BOT_TOKEN, SUPABASE_URL ou SUPABASE_KEY não configuradas!")

# Cliente Supabase
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)