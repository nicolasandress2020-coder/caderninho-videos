"""Coloca no emulador um caderno de exemplo ("Mercearia do Zé") para gravar as telas dos vídeos.

python videos/dados_demo.py
Precisa do emulador ligado e do app instalado. Usa adb root (só funciona no emulador, não em celular de verdade).
APAGA os dados do app no emulador e põe os de exemplo.
"""
import importlib.util
import sqlite3
import subprocess
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ADB = r"C:\android-dev\sdk\platform-tools\adb.exe"
PACOTE = "com.caderninho.fiado"
APARELHO = "DEMO-VIDE"  # código fixo do celular de exemplo
DIA = 86_400_000
FIADO, PAGAMENTO = 1, 2

# (nome, telefone, [(dias atrás, tipo, centavos, descrição)])
CLIENTES = [
    ("Dona Maria", "11 98765-4321", [(47, FIADO, 8650, "Arroz, feijão e óleo"), (31, FIADO, 4290, "Pão e leite da semana"),
                                    (20, PAGAMENTO, 5000, ""), (9, FIADO, 12780, "Compra do mês")]),
    ("Seu João", "11 97654-3210", [(38, FIADO, 15990, "Botijão de gás"), (16, FIADO, 3450, "Café e açúcar")]),
    ("Carla do salão", "11 96543-2109", [(12, FIADO, 6720, "Refrigerantes"), (5, FIADO, 2380, "Biscoitos")]),
    ("Pedro da oficina", "11 95432-1098", [(26, FIADO, 9800, "Marmitas"), (3, PAGAMENTO, 4000, "")]),
    ("Ana Paula", "11 94321-0987", [(8, FIADO, 4475, "Frutas e verduras")]),
    ("Marcos", "11 93210-9876", [(15, FIADO, 5200, "Carne"), (2, PAGAMENTO, 5200, "")]),
    ("Juliana", "11 92109-8765", [(4, FIADO, 3190, "Fraldas")]),
]


def adb(*args, check=True):
    r = subprocess.run([ADB, *args], capture_output=True, text=True, encoding="utf-8")
    if check and r.returncode != 0:
        sys.exit(f"adb {' '.join(args)} falhou: {r.stderr.strip()}")
    return r.stdout


def codigo_ativacao():
    spec = importlib.util.spec_from_file_location("g", RAIZ / "ferramentas" / "gerar-codigo.py")
    g = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(g)
    segredo = (RAIZ / "assinatura" / "segredo-licenca.txt").read_text(encoding="utf-8").strip()
    hoje = g.dia(date.today())
    return g.codigo_ativacao(segredo, APARELHO, hoje + 365), hoje


def banco(caminho: Path):
    agora = int(time.time() * 1000)
    db = sqlite3.connect(caminho)
    db.executescript("""
        CREATE TABLE android_metadata (locale TEXT);
        INSERT INTO android_metadata VALUES ('pt_BR');
        CREATE TABLE clientes (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT NOT NULL,
            telefone TEXT NOT NULL DEFAULT '', criado INTEGER NOT NULL);
        CREATE TABLE lancamentos (id INTEGER PRIMARY KEY AUTOINCREMENT,
            cliente_id INTEGER NOT NULL REFERENCES clientes(id) ON DELETE CASCADE,
            tipo INTEGER NOT NULL, valor INTEGER NOT NULL, descricao TEXT NOT NULL DEFAULT '', data INTEGER NOT NULL);
        CREATE INDEX lanc_cliente ON lancamentos(cliente_id);
        PRAGMA user_version = 1;
    """)
    for nome, tel, lancs in CLIENTES:
        mais_antigo = max(d for d, *_ in lancs)
        cid = db.execute("INSERT INTO clientes (nome, telefone, criado) VALUES (?, ?, ?)",
                         (nome, tel, agora - mais_antigo * DIA)).lastrowid
        for dias, tipo, valor, desc in lancs:
            db.execute("INSERT INTO lancamentos (cliente_id, tipo, valor, descricao, data) VALUES (?, ?, ?, ?, ?)",
                       (cid, tipo, valor, desc, agora - dias * DIA + 3_600_000))
    db.commit()
    db.close()


def preferencias(caminho: Path, ativacao: str, hoje: int):
    caminho.write_text(f"""<?xml version='1.0' encoding='utf-8' standalone='yes' ?>
<map>
    <string name="loja">Mercearia do Zé</string>
    <int name="pix_tipo" value="3" />
    <string name="pix_chave">123e4567-e89b-12d3-a456-426614174000</string>
    <string name="pix_nome">Jose da Silva</string>
    <string name="pix_cidade">Sao Paulo</string>
    <string name="aparelho">{APARELHO}</string>
    <string name="ativacao">{ativacao}</string>
    <boolean name="boas_vindas" value="true" />
    <int name="maior_dia" value="{hoje}" />
</map>
""", encoding="utf-8")


def main():
    ativacao, hoje = codigo_ativacao()
    adb("root")
    time.sleep(2)
    adb("shell", "am", "force-stop", PACOTE)
    adb("shell", "pm", "clear", PACOTE)
    uid = adb("shell", "stat", "-c", "%u", f"/data/data/{PACOTE}").strip()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        banco(tmp / "caderninho.db")
        preferencias(tmp / "config.xml", ativacao, hoje)
        base = f"/data/data/{PACOTE}"
        adb("shell", "mkdir", "-p", f"{base}/databases", f"{base}/shared_prefs")
        adb("push", str(tmp / "caderninho.db"), f"{base}/databases/caderninho.db")
        adb("push", str(tmp / "config.xml"), f"{base}/shared_prefs/config.xml")
    adb("shell", "chown", "-R", f"{uid}:{uid}", f"{base}/databases", f"{base}/shared_prefs")
    adb("shell", "restorecon", "-R", base)
    adb("unroot", check=False)
    print(f"Caderno de exemplo no emulador: {len(CLIENTES)} clientes.")


if __name__ == "__main__":
    main()
