# Reels do Caderninho de Fiado

Vídeos de divulgação do app **Caderninho de Fiado** para o Instagram **@caderninhodefiados**, feitos e postados sozinhos:

1. **Toda segunda**, uma rotina do Claude na nuvem (instruções em [`ROTINA.md`](ROTINA.md)) agenda no Metricool os vídeos prontos e escreve roteiros novos em `roteiros.json`.
2. O **GitHub Actions** ([`.github/workflows/videos.yml`](.github/workflows/videos.yml)) gera os vídeos dos roteiros novos e publica a pasta `saida/` no **GitHub Pages** (o link público que o Metricool usa).
3. O **Metricool** posta no horário marcado, com o PC desligado.

Configuração (conta, horários, posts por semana): [`postagem.json`](postagem.json). O que já foi agendado: [`agenda.json`](agenda.json).

## Gerar no PC

```
pip install -r requirements.txt     # e ffmpeg instalado
python gerar.py                     # todos
python gerar.py 05                  # só os que começam com 05
python gerar.py --faltando          # só os que ainda não têm vídeo
```

Cada roteiro vira `saida/<id>.mp4` (1080x1920, narração e legenda), `saida/<id>.jpg` (capa) e `saida/<id>.txt` (texto do post).

As telas em `telas/` são do app de verdade com um caderno de exemplo. Para gravá-las de novo é preciso o projeto do app e o emulador (`dados_demo.py` e `capturar.py`, que só rodam dentro da pasta do app).

Fonte: Montserrat ([SIL Open Font License](fontes/OFL.txt)). Voz: edge-tts (pt-BR-FranciscaNeural).
