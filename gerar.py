"""Gera os Reels de divulgação do app a partir de videos/roteiros.json e das telas em videos/telas/.

python gerar.py                 gera todos
python gerar.py 02              só os que começam com "02"
python gerar.py --faltando      só os que ainda não têm .mp4 em saida/ (usado pelo GitHub Actions)

Saída em videos/saida/: <id>.mp4 (1080x1920, 30 fps, com narração), <id>.jpg (capa) e <id>.txt (legenda do post).
Narração: edge-tts (precisa de internet; fica em cache em videos/.cache). Vídeo: Pillow + ffmpeg.
"""
import asyncio
import hashlib
import importlib.util
import json
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

AQUI = Path(__file__).resolve().parent
TELAS, SAIDA, CACHE = AQUI / "telas", AQUI / "saida", AQUI / ".cache"
W, H, FPS, TAXA = 1080, 1920, 30, 44100

VERDE, AZUL = (18, 128, 92), (14, 108, 140)
AMARELO, BRANCO, ESCURO = (255, 200, 61), (255, 255, 255), (13, 21, 18)
# Fonte livre (OFL) junto do projeto: funciona igual no Windows e no Linux da nuvem.
FONTE = AQUI / "fontes" / "Montserrat.ttf"
NEGRITO, NORMAL, MONO = "Bold", "Medium", "Regular"  # pesos da fonte variável

# Geometria do celular (na escala normal): tela de 1080x2400 reduzida para esta altura.
TELA_ALT = 1240
TELA_LARG = round(TELA_ALT * 1080 / 2400)
MOLDURA, MARGEM, ESCALA_MAX = 18, 40, 1.7
TOPO_CELULAR = 520
ALVO_FOCO = (540, 1000)  # para onde o zoom leva a parte em destaque
LEG_Y = 1390  # legenda (acima da área que o Instagram cobre)

_fontes = {}


def fonte(tam, peso=NEGRITO):
    chave = (peso, tam)
    if chave not in _fontes:
        f = ImageFont.truetype(str(FONTE), tam)
        f.set_variation_by_name(peso)
        _fontes[chave] = f
    return _fontes[chave]


def suave(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


# ---------- narração ----------

def narrar(texto, voz, velocidade):
    """Narração em PCM 16 bits mono (numpy), com cache."""
    CACHE.mkdir(exist_ok=True)
    h = hashlib.sha1(f"{voz}|{velocidade}|{texto}".encode()).hexdigest()[:16]
    wav = CACHE / f"{h}.wav"
    if not wav.exists():
        import edge_tts
        mp3 = CACHE / f"{h}.mp3"
        asyncio.run(edge_tts.Communicate(texto, voz, rate=velocidade).save(str(mp3)))
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3), "-ac", "1", "-ar", str(TAXA), str(wav)], check=True)
        mp3.unlink()
    with wave.open(str(wav)) as w:
        a = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
    # A voz vem com silêncio no começo e ~0,8 s no fim: corta, senão a legenda atrasa e o ritmo fica lento.
    som = np.where(np.abs(a.astype(np.int32)) > 600)[0]
    if len(som):
        a = a[max(0, som[0] - int(0.03 * TAXA)):som[-1] + int(0.08 * TAXA)]
    return a


# ---------- peças visuais (feitas uma vez) ----------

def fundo():
    y, x = np.mgrid[0:H, 0:W].astype(np.float32)
    t = np.clip((x / W) * 0.35 + (y / H) * 0.65, 0, 1)[..., None]
    img = np.array(VERDE, np.float32) * (1 - t) + np.array(AZUL, np.float32) * t
    luz = np.exp(-(((x - W * 0.25) / (W * 0.7)) ** 2 + ((y - H * 0.18) / (H * 0.35)) ** 2))[..., None]
    img = img + luz * 28
    pontos = ((x % 36 < 3) & (y % 36 < 3))[..., None]  # textura de pontinhos bem leve
    img = img + pontos * 6
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).convert("RGBA")


FAIXA = 500


def faixa(fundo_img):
    """Topo com o fundo por cima do celular: o celular passa por baixo do título quando dá zoom."""
    f = fundo_img.crop((0, 0, W, FAIXA))
    a = np.full((FAIXA, W), 255, np.uint8)
    a[FAIXA - 60:] = np.linspace(255, 0, 60, dtype=np.uint8)[:, None]
    f.putalpha(Image.fromarray(a))
    return f


def celular(tela):
    """Celular com moldura e sombra, já na escala máxima (diminui a cada quadro)."""
    k = ESCALA_MAX
    sw, sh, b, m = round(TELA_LARG * k), round(TELA_ALT * k), round(MOLDURA * k), round(MARGEM * k)
    img = Image.new("RGBA", (sw + 2 * (b + m), sh + 2 * (b + m)), (0, 0, 0, 0))
    sombra = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sombra).rounded_rectangle([m, m + 18 * k, m + sw + 2 * b, m + sh + 2 * b + 18 * k], 70 * k, fill=(0, 0, 0, 120))
    img = Image.alpha_composite(img, sombra.filter(ImageFilter.GaussianBlur(22 * k)))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([m, m, m + sw + 2 * b, m + sh + 2 * b], 68 * k, fill=ESCURO + (255,))
    shot = Image.open(TELAS / f"{tela}.png").convert("RGBA").resize((sw, sh), Image.LANCZOS)
    mascara = Image.new("L", (sw, sh), 0)
    ImageDraw.Draw(mascara).rounded_rectangle([0, 0, sw, sh], 52 * k, fill=255)
    img.paste(shot, (m + b, m + b), mascara)
    return img


def no_celular(x, y):
    """Ponto da captura (1080x2400) → ponto na imagem do celular na escala normal."""
    f = TELA_LARG / 1080
    return MARGEM + MOLDURA + x * f, MARGEM + MOLDURA + y * f


def texto_centralizado(d, linhas, y, tam, cor, largura_max=960, arquivo=NEGRITO, espaco=1.12, sombra=True):
    """Desenha linhas centralizadas; diminui a fonte até caber. Devolve o y do fim."""
    while tam > 30 and max(d.textlength(l, font=fonte(tam, arquivo)) for l in linhas) > largura_max:
        tam -= 4
    f = fonte(tam, arquivo)
    for l in linhas:
        x = (W - d.textlength(l, font=f)) / 2
        if sombra:
            d.text((x + 3, y + 5), l, font=f, fill=(0, 0, 0, int(cor[3] * 0.25) if len(cor) > 3 else 60))
        d.text((x, y), l, font=f, fill=cor)
        y += tam * espaco
    return y


# ---------- cenas ----------

class Cena:
    def __init__(self, dados, audio, inicio, dur, extras):
        self.d, self.audio, self.inicio, self.dur, self.x = dados, audio, inicio, dur, extras
        self.tipo = dados["tipo"]
        self.legendas = self.pedacos() if self.tipo in ("tela", "mensagem") else []
        self.leg_y = LEG_Y

    def pedacos(self):
        """Legenda em pedaços de poucas palavras, com o tempo proporcional ao tamanho."""
        palavras, grupos, atual = self.d.get("fala", "").split(), [], []
        for p in palavras:
            if atual and (len(" ".join(atual + [p])) > 22 or atual[-1][-1] in ",.:?!"):
                grupos.append(" ".join(atual))
                atual = []
            atual.append(p)
        if atual:
            grupos.append(" ".join(atual))
        fala = len(self.audio) / TAXA
        total = sum(len(g) + 3 for g in grupos) or 1
        t, saida = 0.12, []
        for g in grupos:
            dt = fala * (len(g) + 3) / total
            saida.append((t, t + dt, g))
            t += dt
        return saida

    def desenhar(self, quadro, u):
        camada = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(camada)
        if self.tipo == "tela":
            self.tela(quadro, d, u)
        elif self.tipo == "mensagem":
            self.mensagem(quadro, d, u)
        elif self.tipo == "texto":
            self.texto(quadro, u)
        elif self.tipo == "fim":
            self.fim(quadro, d, u)
        if self.tipo in ("tela", "mensagem"):
            self.titulo(d, u)
            self.legenda(d, u)
        return Image.alpha_composite(quadro, camada)

    def titulo(self, d, u):
        a = suave(u / 0.35)
        texto_centralizado(d, self.d["titulo"].split("\n"), 230 + (1 - a) * 40, 84, BRANCO + (int(255 * a),))

    def legenda(self, d, u):
        for ini, fim, g in self.legendas:
            if ini <= u < fim + 0.08:
                f = fonte(56)
                x = (W - d.textlength(g, font=f)) / 2
                y = self.leg_y
                d.rounded_rectangle([x - 26, y - 10, x + d.textlength(g, font=f) + 26, y + 78], 24, fill=(0, 0, 0, 165))
                d.text((x, y), g, font=f, fill=AMARELO + (255,))
                break

    def tela(self, quadro, d, u):
        cel = self.x["celulares"][self.d["tela"]]
        x0, y0, x1, y1 = self.d.get("foco", [0, 0, 1080, 2400])
        z = self.d.get("zoom", 1.0)
        e = suave(u / 1.0)
        s = 1 + (z - 1) * e + 0.025 * max(0.0, u - 1.0)  # zoom e um leve "respiro" depois
        fx, fy = no_celular((x0 + x1) / 2, (y0 + y1) / 2)
        base = ((W - cel.width / ESCALA_MAX) / 2, TOPO_CELULAR - MARGEM)
        px = base[0] + fx + (ALVO_FOCO[0] - (base[0] + fx)) * e
        py = base[1] + fy + (ALVO_FOCO[1] - (base[1] + fy)) * e
        ox, oy = px - fx * s, py - fy * s
        # Foco num canto (ex.: botão Recebi): não deixa o celular sair pelos lados da tela.
        largura = cel.width * s / ESCALA_MAX
        sobra = MARGEM * s  # a sombra em volta pode ficar para fora
        if largura - 2 * sobra <= W:
            ox = min(max(ox, -sobra), W - largura + sobra)
        else:
            ox = min(max(ox, W - largura + sobra), -sobra)
        # Legenda logo abaixo da parte em destaque (para não tapar outra coisa do app).
        _, fundo_y = no_celular(0, y1)
        self.leg_y = int(min(max(oy + fundo_y * s + 40, 1180), 1560))
        pequeno = cel.resize((round(cel.width * s / ESCALA_MAX), round(cel.height * s / ESCALA_MAX)), Image.BILINEAR)
        quadro.alpha_composite(pequeno, (round(ox), round(oy)))
        quadro.alpha_composite(self.x["faixa"], (0, 0))
        d.text((W - 50, FAIXA - 70), "dados de exemplo", font=fonte(28, NORMAL), fill=(255, 255, 255, 140), anchor="ra")
        # Destaque amarelo em volta da parte importante.
        if u > 0.75:
            a = suave((u - 0.75) / 0.3)
            ax0, ay0 = no_celular(x0, y0)
            ax1, ay1 = no_celular(x1, y1)
            caixa = [ox + ax0 * s - 14, oy + ay0 * s - 14, ox + ax1 * s + 14, oy + ay1 * s + 14]
            d.rounded_rectangle(caixa, 34, outline=AMARELO + (int(255 * a),), width=9)
        # Toque no botão.
        if self.d.get("toque") and 1.0 < u < 1.9:
            k = (u - 1.0) / 0.9
            cx, cy = ox + fx * s, oy + fy * s
            r = 30 + 80 * suave(k)
            d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(255, 255, 255, int(230 * (1 - k))), width=8)
            d.ellipse([cx - 26, cy - 26, cx + 26, cy + 26], fill=(255, 255, 255, int(200 * (1 - k))))

    def mensagem(self, quadro, d, u):
        a = suave(u / 0.3)
        msg, pix = self.x["mensagem"]
        f, entre = fonte(44, NORMAL), 58
        final = quebrar(d, msg, f, 740)
        balao_final = entre * len(final) + 150
        cx0, cx1 = 60, W - 60
        cy0 = 470 + (1 - a) * 50
        cy1 = cy0 + 130 + 40 + balao_final + 50
        d.rounded_rectangle([cx0 + 6, cy0 + 14, cx1 + 6, cy1 + 14], 44, fill=(0, 0, 0, int(70 * a)))
        d.rounded_rectangle([cx0, cy0, cx1, cy1], 44, fill=(238, 243, 238, int(255 * a)))
        d.rounded_rectangle([cx0, cy0, cx1, cy0 + 130], 44, fill=VERDE + (int(255 * a),))
        d.rectangle([cx0, cy0 + 90, cx1, cy0 + 130], fill=VERDE + (int(255 * a),))
        d.ellipse([cx0 + 34, cy0 + 28, cx0 + 108, cy0 + 102], fill=(225, 241, 232, int(255 * a)))
        d.text((cx0 + 71, cy0 + 65), "DM", font=fonte(30), fill=VERDE + (int(255 * a),), anchor="mm")
        d.text((cx0 + 132, cy0 + 36), "Dona Maria", font=fonte(44), fill=(255, 255, 255, int(255 * a)))
        # Balão com a mensagem sendo "digitada".
        progresso = min(1.0, max(0.0, (u - 0.3) / max(0.8, self.dur * 0.7)))
        linhas = quebrar(d, msg[:int(len(msg) * progresso)], f, 740)
        bx0, by0 = cx0 + 60, cy0 + 170
        alt = entre * max(1, len(linhas)) + (150 if progresso >= 1 else 0) + 40
        d.rounded_rectangle([bx0, by0, cx1 - 30, by0 + alt], 30, fill=(214, 240, 222, int(255 * a)))
        y = by0 + 22
        for l in linhas:
            d.text((bx0 + 30, y), l, font=f, fill=(23, 35, 28, int(255 * a)))
            y += entre
        if progresso >= 1:
            d.text((bx0 + 30, y + 10), "Pix copia e cola:", font=fonte(40), fill=(23, 35, 28, 255))
            d.text((bx0 + 30, y + 66), pix[:34] + "…", font=fonte(34, MONO), fill=(60, 80, 70, 255))

    def texto(self, quadro, u):
        a = suave(u / 0.35)
        s = 0.86 + 0.14 * a
        camada = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(camada)
        linhas = self.d["titulo"].split("\n")
        tam = 118
        y0 = 830 - len(linhas) * tam * 1.12 / 2
        y = texto_centralizado(d, linhas, y0, tam, BRANCO + (255,), largura_max=980)
        if self.d.get("sub"):
            sub = self.d["sub"]
            f = fonte(56)
            larg = d.textlength(sub, font=f)
            d.rounded_rectangle([(W - larg) / 2 - 34, y + 30, (W + larg) / 2 + 34, y + 130], 50, fill=AMARELO + (255,))
            d.text(((W - larg) / 2, y + 40), sub, font=f, fill=ESCURO + (255,))
        camada = camada.resize((round(W * s), round(H * s)), Image.BILINEAR)
        alfa = camada.getchannel("A").point(lambda v: int(v * a))
        camada.putalpha(alfa)
        quadro.alpha_composite(camada, (round((W - camada.width) / 2), round((H - camada.height) / 2)))

    def fim(self, quadro, d, u):
        fim = self.x["fim"]
        a = suave(u / 0.35)
        icone = self.x["icone"]
        s = 0.7 + 0.3 * suave(u / 0.45)
        ic = icone.resize((round(300 * s), round(300 * s)), Image.LANCZOS)
        quadro.alpha_composite(ic, (round((W - ic.width) / 2), round(470 - ic.height / 2)))
        y = texto_centralizado(d, ["Caderninho de Fiado"], 660, 70, BRANCO + (int(255 * a),))
        y = texto_centralizado(d, [fim["titulo"]], y + 60, 120, BRANCO + (int(255 * a),))
        f = fonte(62)
        larg = d.textlength(fim["sub"], font=f)
        b = suave((u - 0.3) / 0.35)
        d.rounded_rectangle([(W - larg) / 2 - 44, y + 34, (W + larg) / 2 + 44, y + 150], 58, fill=(255, 255, 255, int(255 * b)))
        d.text(((W - larg) / 2, y + 46), fim["sub"], font=f, fill=VERDE + (int(255 * b),))
        texto_centralizado(d, [fim["preco"]], y + 200, 64, AMARELO + (int(255 * b),))


def quebrar(d, texto, f, largura):
    linhas = []
    for paragrafo in texto.split("\n"):
        atual = ""
        for p in paragrafo.split(" "):
            teste = (atual + " " + p).strip()
            if d.textlength(teste, font=f) > largura and atual:
                linhas.append(atual)
                atual = p
            else:
                atual = teste
        linhas.append(atual)
    return linhas


# ---------- montagem ----------

def mensagem_cobranca():
    spec = importlib.util.spec_from_file_location("pix", AQUI / "pix.py")
    v = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(v)
    pix = v.copia_e_cola("123e4567-e89b-12d3-a456-426614174000", "Jose da Silva", "Sao Paulo", 20720)
    msg = ("Olá, Dona Maria! Tudo bem? Aqui é da Mercearia do Zé. Passando para lembrar do seu fiado, "
           "que está em R$ 207,20. Quando puder, é só pagar pelo Pix abaixo (copie e cole no app do banco). Obrigado!")
    return msg, pix


def gerar(video, cfg, extras):
    voz, vel = cfg["voz"], cfg["velocidade"]
    cenas, partes, t = [], [np.zeros(int(TAXA * 0.15), np.int16)], 0.15
    for c in video["cenas"]:
        dados = dict(cfg["fim"], tipo="fim") if c["tipo"] == "fim" else c
        audio = narrar(dados["fala"], voz, vel)
        dur = max(len(audio) / TAXA + (0.9 if c["tipo"] == "fim" else 0.4), 1.6)
        cenas.append(Cena(dados, audio, t, dur, extras))
        som = np.zeros(int(round(dur * TAXA)), np.int16)
        som[:len(audio)] = audio[:len(som)]
        partes.append(som)
        t += dur
    total = t
    SAIDA.mkdir(exist_ok=True)
    wav = CACHE / f"{video['id']}.wav"
    with wave.open(str(wav), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(TAXA)
        w.writeframes(np.concatenate(partes).tobytes())

    mp4 = SAIDA / f"{video['id']}.mp4"
    ff = subprocess.Popen(["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
                           "-r", str(FPS), "-i", "-", "-i", str(wav), "-c:v", "libx264", "-preset", "medium", "-crf", "19",
                           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-af", "loudnorm=I=-16:TP=-1.5",
                           "-shortest", "-movflags", "+faststart", str(mp4)], stdin=subprocess.PIPE)
    fundo_img = extras["fundo"]
    n = int(total * FPS)
    for i in range(n):
        tempo = i / FPS
        cena = next((c for c in cenas if c.inicio <= tempo < c.inicio + c.dur), cenas[-1] if tempo >= cenas[0].inicio else cenas[0])
        quadro = cena.desenhar(fundo_img.copy(), max(0.0, tempo - cena.inicio))
        if i == int(0.9 * FPS):
            quadro.convert("RGB").save(SAIDA / f"{video['id']}.jpg", quality=90)
        ff.stdin.write(quadro.convert("RGB").tobytes())
    ff.stdin.close()
    if ff.wait() != 0:
        sys.exit(f"ffmpeg falhou em {video['id']}")
    (SAIDA / f"{video['id']}.txt").write_text(video["legenda"] + "\n\n" + cfg["hashtags"] + "\n", encoding="utf-8")
    print(f"✓ {mp4.name}  ({total:.1f} s)")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    cfg = json.loads((AQUI / "roteiros.json").read_text(encoding="utf-8"))
    filtro = sys.argv[1] if len(sys.argv) > 1 else ""
    so_faltando = filtro == "--faltando"
    if so_faltando:
        filtro = ""
    telas = {c["tela"] for v in cfg["videos"] for c in v["cenas"] if c["tipo"] == "tela"}
    faltando = [t for t in telas if not (TELAS / f"{t}.png").exists()]
    if faltando:
        sys.exit(f"Faltam telas em telas/: {faltando}. Rode capturar.py (precisa do emulador)")
    extras = {
        "fundo": fundo(),
        "faixa": None,
        "celulares": {t: celular(t) for t in telas},
        "icone": Image.open(AQUI / "icone.png").convert("RGBA"),
        "mensagem": mensagem_cobranca(),
        "fim": cfg["fim"],
    }
    extras["faixa"] = faixa(extras["fundo"])
    feitos = 0
    for v in cfg["videos"]:
        if not v["id"].startswith(filtro):
            continue
        if so_faltando and (SAIDA / f"{v['id']}.mp4").exists():
            continue
        gerar(v, cfg, extras)
        feitos += 1
    print(f"{feitos} vídeo(s) gerado(s)")


if __name__ == "__main__":
    main()
