"""Grava as telas do app (emulador com o caderno de exemplo) em videos/telas/*.png, em resolução cheia.

python videos/dados_demo.py   (antes, uma vez)
python videos/capturar.py
"""
import subprocess
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ADB = r"C:\android-dev\sdk\platform-tools\adb.exe"
TELAS = Path(__file__).resolve().parent / "telas"
PACOTE = "com.caderninho.fiado"


def adb(*args):
    return subprocess.run([ADB, *args], capture_output=True, encoding="utf-8").stdout


def ui(*args):
    r = subprocess.run([sys.executable, str(RAIZ / "testes" / "ui.py"), *args], capture_output=True, encoding="utf-8")
    if r.returncode != 0:
        sys.exit(f"ui.py {args} falhou: {r.stdout}{r.stderr}")
    time.sleep(1.2)


def foto(nome):
    time.sleep(0.8)
    png = subprocess.run([ADB, "exec-out", "screencap", "-p"], capture_output=True).stdout
    (TELAS / f"{nome}.png").write_bytes(png)
    print("✓", nome)


def barra_limpa(ligar=True):
    """Modo demonstração do Android: relógio 9:30, bateria cheia, sem notificações."""
    if not ligar:
        adb("shell", "am", "broadcast", "-a", "com.android.systemui.demo", "-e", "command", "exit")
        return
    adb("shell", "settings", "put", "global", "sysui_demo_allowed", "1")
    for extra in (["clock", "-e", "hhmm", "0930"], ["battery", "-e", "level", "100", "-e", "plugged", "false"],
                  ["network", "-e", "wifi", "show", "-e", "level", "4", "-e", "mobile", "show", "-e", "datatype", "4g", "-e", "level", "4"],
                  ["notifications", "-e", "visible", "false"]):
        adb("shell", "am", "broadcast", "-a", "com.android.systemui.demo", "-e", "command", "enter")
        adb("shell", "am", "broadcast", "-a", "com.android.systemui.demo", "-e", "command", *extra)


def main():
    TELAS.mkdir(exist_ok=True)
    adb("shell", "am", "force-stop", PACOTE)
    barra_limpa()
    adb("shell", "monkey", "-p", PACOTE, "-c", "android.intent.category.LAUNCHER", "1")
    time.sleep(3)
    foto("lista")

    ui("tocar", "Dona Maria")
    foto("cliente")

    ui("tocar", "Anotar fiado")
    ui("campo", "Ex.: 25,90", "23,50")
    ui("campo", "Ex.: pão, leite e café", "Leite e biscoito")  # adb não digita acento
    adb("shell", "input", "keyevent", "KEYCODE_BACK")  # fecha o teclado
    foto("anotar")
    adb("shell", "input", "keyevent", "KEYCODE_BACK")  # fecha a janela sem salvar
    time.sleep(1)
    adb("shell", "input", "keyevent", "KEYCODE_BACK")  # volta para a lista
    time.sleep(1)

    ui("tocar", "Relatório do mês")
    ui("tocar", "Mês anterior")  # o mês atual pode estar começando, sem movimento
    foto("relatorio")
    adb("shell", "input", "keyevent", "KEYCODE_BACK")
    barra_limpa(False)


if __name__ == "__main__":
    main()
