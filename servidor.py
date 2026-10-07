# servidor.py
"""
Controlador do servidor Central VigiaSaúde.

Uso:
    python servidor.py start      → inicia o bot
    python servidor.py stop       → para o bot
    python servidor.py restart    → reinicia
    python servidor.py status     → mostra se está rodando
    python servidor.py logs       → mostra últimas linhas do log
"""
import os
import sys
import time
import signal
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
PID_FILE = BASE_DIR / "servidor.pid"
LOG_FILE = BASE_DIR / "servidor.log"
BOT_SCRIPT = "main.py"


def _ler_pid() -> int | None:
    if not PID_FILE.exists():
        return None
    try:
        return int(PID_FILE.read_text().strip())
    except Exception:
        return None


def _esta_rodando(pid: int | None) -> bool:
    if pid is None:
        return False
    try:
        if sys.platform == "win32":
            output = subprocess.check_output(
                ["tasklist", "/FI", f"PID eq {pid}"],
                stderr=subprocess.DEVNULL,
                text=True,
            )
            return str(pid) in output
        else:
            os.kill(pid, 0)
            return True
    except Exception:
        return False


def _matar_processo(pid: int):
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(pid)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            os.kill(pid, signal.SIGTERM)
            time.sleep(2)
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
    except Exception as e:
        print(f"⚠️  Erro ao matar processo {pid}: {e}")


def _limpar_pid():
    if PID_FILE.exists():
        PID_FILE.unlink()


def start():
    """Inicia o bot em background."""
    pid = _ler_pid()

    # 🧹 Limpa PID órfão automaticamente
    if pid and not _esta_rodando(pid):
        print(f"🧹 Limpando PID órfão ({pid})...")
        _limpar_pid()
        pid = None

    if _esta_rodando(pid):
        print(f"⚠️  O bot JÁ ESTÁ rodando (PID {pid}).")
        print(f"   Use: python servidor.py status")
        return

    print("🚀 Iniciando Central VigiaSaúde...")

    log_handle = open(LOG_FILE, "a", encoding="utf-8")

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    if sys.platform == "win32":
        proc = subprocess.Popen(
            [sys.executable, "-u", BOT_SCRIPT],
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            cwd=str(BASE_DIR),
            env=env,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW,
        )
    else:
        proc = subprocess.Popen(
            [sys.executable, "-u", BOT_SCRIPT],
            stdout=log_handle,
            stderr=subprocess.STDOUT,
            cwd=str(BASE_DIR),
            env=env,
            start_new_session=True,
        )

    PID_FILE.write_text(str(proc.pid))

    time.sleep(3)
    if _esta_rodando(proc.pid):
        print(f"✅ Bot iniciado com sucesso! (PID {proc.pid})")
        print(f"📄 Log: {LOG_FILE}")
    else:
        print("❌ Falha ao iniciar. Verifique os logs:")
        print(f"   python servidor.py logs")


def stop():
    pid = _ler_pid()
    if not pid:
        print("ℹ️  Nenhum bot rodando (PID não encontrado).")
        return

    if not _esta_rodando(pid):
        print(f"ℹ️  Processo {pid} não está ativo. Limpando arquivo de PID...")
        _limpar_pid()
        return

    print(f"🛑 Parando bot (PID {pid})...")
    _matar_processo(pid)
    _limpar_pid()
    print("✅ Bot parado.")


def status():
    pid = _ler_pid()
    if _esta_rodando(pid):
        print(f"🟢 Bot RODANDO")
        print(f"   PID: {pid}")
        print(f"   Log: {LOG_FILE}")
        if LOG_FILE.exists():
            tamanho = LOG_FILE.stat().st_size / 1024
            print(f"   Tamanho do log: {tamanho:.1f} KB")
    else:
        print("🔴 Bot PARADO")
        if pid:
            print(f"   (arquivo de PID órfão: {pid})")


def logs(linhas: int = 50):
    if not LOG_FILE.exists():
        print("ℹ️  Nenhum log encontrado.")
        return

    print(f"📄 Últimas {linhas} linhas de {LOG_FILE.name}:\n")
    print("─" * 60)

    with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
        todas = f.readlines()
        for linha in todas[-linhas:]:
            print(linha.rstrip())

    print("─" * 60)


def restart():
    print("🔄 Reiniciando...")
    stop()
    time.sleep(2)
    start()


def ajuda():
    print("""
╔══════════════════════════════════════════════╗
║  CONTROLADOR DO SERVIDOR CENTRAL VIGIASAÚDE  ║
╚══════════════════════════════════════════════╝

Comandos disponíveis:

  python servidor.py start      → Inicia o bot em background
  python servidor.py stop       → Para o bot
  python servidor.py restart    → Reinicia o bot
  python servidor.py status     → Mostra se está rodando
  python servidor.py logs       → Mostra últimas 50 linhas do log
  python servidor.py logs 200   → Mostra últimas 200 linhas
  python servidor.py help       → Mostra esta ajuda
""")


def main():
    if len(sys.argv) < 2:
        ajuda()
        return

    comando = sys.argv[1].lower()

    if comando == "start":
        start()
    elif comando == "stop":
        stop()
    elif comando == "restart":
        restart()
    elif comando == "status":
        status()
    elif comando == "logs":
        n = 50
        if len(sys.argv) > 2:
            try:
                n = int(sys.argv[2])
            except ValueError:
                pass
        logs(n)
    elif comando in ("help", "-h", "--help", "ajuda"):
        ajuda()
    else:
        print(f"❌ Comando desconhecido: {comando}")
        ajuda()


if __name__ == "__main__":
    main()