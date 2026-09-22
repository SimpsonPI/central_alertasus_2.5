from dotenv import load_dotenv
import os

print("CWD:", os.getcwd())

# Teste 1: load_dotenv padrão
resultado = load_dotenv()
print("load_dotenv() retornou:", resultado)
print("SUPABASE_URL:", os.getenv("SUPABASE_URL"))
print("SUPABASE_KEY:", (os.getenv("SUPABASE_KEY") or "VAZIO")[:30])

# Teste 2: load_dotenv com caminho absoluto
os.environ.pop("SUPABASE_URL", None)
os.environ.pop("SUPABASE_KEY", None)

caminho = os.path.join(os.getcwd(), ".env")
print("\nTentando caminho absoluto:", caminho)
resultado2 = load_dotenv(dotenv_path=caminho, override=True)
print("load_dotenv(caminho) retornou:", resultado2)
print("SUPABASE_URL:", os.getenv("SUPABASE_URL"))
print("SUPABASE_KEY:", (os.getenv("SUPABASE_KEY") or "VAZIO")[:30])