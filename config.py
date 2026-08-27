import os
from dotenv import load_dotenv
load_dotenv()

BOT_PUBLICO_TOKEN = os.getenv("BOT_PUBLICO_TOKEN")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
MERCADO_PAGO_ACCESS_TOKEN = os.getenv("MERCADO_PAGO_ACCESS_TOKEN")
BOT_PRINCIPAL_LINK = os.getenv("BOT_PRINCIPAL_LINK")