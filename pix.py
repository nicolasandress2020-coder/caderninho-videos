"""Pix copia e cola (BR Code estático), igual ao do app. Usado só para a cena da mensagem de cobrança."""
import re
import unicodedata


def crc16(s: str) -> str:
    crc = 0xFFFF
    for b in s.encode("utf-8"):
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else crc << 1
            crc &= 0xFFFF
    return f"{crc:04X}"


def limpar(s: str, maximo: int) -> str:
    t = "".join(c for c in unicodedata.normalize("NFD", s or "") if not unicodedata.combining(c))
    t = re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9 .\-]", "", t)).strip()
    return t[:maximo].strip() if len(t) > maximo else t


def campo(i: str, v: str) -> str:
    return f"{i}{len(v):02d}{v}"


def copia_e_cola(chave: str, nome: str, cidade: str, centavos: int) -> str:
    n = limpar(nome, 25) or "Recebedor"
    c = limpar(cidade, 15) or "Brasil"
    s = campo("00", "01") + campo("26", campo("00", "br.gov.bcb.pix") + campo("01", chave))
    s += campo("52", "0000") + campo("53", "986")
    if centavos > 0:
        s += campo("54", f"{centavos // 100}.{centavos % 100:02d}")
    s += campo("58", "BR") + campo("59", n) + campo("60", c) + campo("62", campo("05", "***")) + "6304"
    return s + crc16(s)
