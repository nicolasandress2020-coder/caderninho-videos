# Rotina semanal (agente na nuvem)

Você cuida dos Reels do Instagram **@caderninhodefiados**, que divulgam o app Android **Caderninho de Fiado** (comerciante anota o fiado de cada cliente, vê o total a receber e cobra pelo WhatsApp com o Pix pronto; assinatura de R$ 29,99 por ano; pedido pelo Direct do Instagram).

Configuração em `postagem.json`. Faça, nesta ordem:

## 1. Conferir a conta (trava de segurança)

Chame `getBrandSettings` do Metricool. Ache a marca com o `id` igual a `metricool_blog_id`. Se o `networksData.instagramData` dela **não** for exatamente o valor de `instagram` em `postagem.json`, **não agende nada** (seria postar na conta errada): pule para o passo 3 e termine dizendo isso no resumo.

## 2. Agendar os vídeos prontos

Um vídeo está pronto quando existe `saida/<id>.mp4` no repositório **e** o link `<pages_url>/<id>.mp4` responde 200 (`curl -sI`). Para cada vídeo pronto que **não** está em `agenda.json`, na ordem de `roteiros.json`:

- Escolha o próximo horário livre entre os `horarios` de `postagem.json` (fuso `America/Sao_Paulo`), a partir de amanhã, sem repetir dia que já tenha post (confira `agenda.json` e `getScheduledPosts`). No máximo `posts_por_semana` por semana.
- Agende com `createScheduledPost`: `blogId` = `metricool_blog_id`; `providers` = `[{"network":"instagram"}]`; `instagramData` = `{"type":"REEL","showReelOnFeed":true,"isAiGenerated":true}`; `text` = conteúdo de `saida/<id>.txt`; `media` = `["<pages_url>/<id>.mp4"]`; `videoThumbnailUrl` = `"<pages_url>/<id>.jpg"`; `autoPublish` = true; `draft` = false.
- Anote em `agenda.json`: `"<id>": {"data": "<ISO com fuso>", "planner": "<plannerUrl da resposta>"}`.
- Agende no máximo 6 por execução.

## 3. Escrever roteiros novos

Conte quantos roteiros ainda **não** estão em `agenda.json` (prontos ou ainda sem vídeo). Se forem menos que `posts_por_semana`, escreva os que faltam para chegar a `posts_por_semana` e acrescente no fim de `videos` em `roteiros.json`.

Regras de cada roteiro (copie o formato dos que já existem):
- `id`: número seguinte com 2 dígitos + nome curto, ex. `13-cliente-sumiu`.
- 3 a 5 cenas + a cena final `{"tipo": "fim"}`. O vídeo deve ter de 15 a 25 segundos: cada `fala` com até 15 palavras, frases simples, em português do Brasil falado.
- 1ª cena: `texto` com um **gancho** forte (pergunta ou situação do dia a dia de quem vende fiado), diferente de todos os ganchos que já existem.
- Cenas `tela` só com as telas `lista`, `cliente`, `anotar`, `relatorio`, usando os focos da tabela abaixo. `titulo` com até 2 linhas curtas (use `\n`). Use `"toque": true` só nos botões.
- Pode usar `mensagem` (mostra a cobrança pronta com o Pix) e `texto` (com `sub` opcional).
- `legenda`: 2 a 4 frases + linha final exatamente `R$ 29,99 por ano. Peça o app aqui no Direct 📩`. Pode ter 1 ou 2 emojis.
- Não invente funções que o app não tem (ele **não** tem: estoque, nota fiscal, vários usuários, versão para iPhone, cobrança automática). Não cite concorrentes, não use depoimento de cliente, não prometa ganho de dinheiro. Os dados nas telas são de exemplo.
- Valide: `python -c "import json; json.load(open('roteiros.json', encoding='utf-8'))"`.

Focos (coordenadas na captura 1080x2400) e zoom sugerido:

| tela | parte | foco | zoom |
|---|---|---|---|
| lista | total a receber | [42, 306, 1038, 594] | 1.45 |
| lista | 2 clientes atrasados (vermelho) | [42, 780, 1038, 1158] | 1.55 |
| lista | lista inteira | [42, 780, 1038, 1600] | 1.2 |
| cliente | total devendo + desde quando | [42, 300, 1038, 654] | 1.45 |
| cliente | botão Cobrar no WhatsApp | [42, 843, 1038, 972] | 1.5 |
| cliente | botão Recebi | [552, 687, 1038, 816] | 1.4 |
| cliente | histórico de compras | [42, 1100, 1038, 1800] | 1.3 |
| anotar | janela de anotar fiado | [69, 789, 1008, 1680] | 1.3 |
| relatorio | saiu fiado x recebido | [42, 459, 1038, 711] | 1.45 |
| relatorio | quem deve mais | [42, 1050, 1038, 1584] | 1.35 |

## 4. Limpar

Apague `saida/<id>.mp4` dos vídeos com `data` em `agenda.json` há mais de 14 dias (o Instagram já tem a cópia). Mantenha o `.txt` e o `.jpg`.

## 5. Salvar

`git add -A && git commit -m "Rotina semanal: agenda e roteiros" && git push` na branch `main`. O GitHub Actions gera os vídeos novos e eles são agendados na próxima execução.

Termine com um resumo curto: o que agendou (id e data), quais roteiros escreveu e qualquer problema.
