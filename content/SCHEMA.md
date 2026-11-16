# Arquivos de tópicos curados (`content/topics/<id>.json`)

Cada arquivo representa uma "necessidade" no aplicativo (**Último Livro**, fork brasileiro do **Lastbook**). O aplicativo exibe, nesta ordem:
1. o título (`title`) e uma introdução curta em uma frase (`intro`),
2. **choices** ("O que está acontecendo?") — a pessoa toca em uma situação e vê de 1 a 4 leituras recomendadas para ela,
3. **limits** — quando a própria fonte indica parar, buscar ajuda profissional ou acionar socorro especializado,
4. **prepare** — leituras para se preparar antes que o problema aconteça,
5. **learn** — manuais completos, vídeos e artigos de enciclopédia para estudo aprofundado,
6. em trilhas de aprendizagem (`mode: "learn"`), um roteiro ordenado (**route**) de etapas do nível iniciante ao avançado (`"Etapa 1: ..."`).

Dados bibliográficos das fontes (editor/órgão, edição, data, tipo de arquivo, número de páginas, duração do vídeo, transcrição) são preenchidos automaticamente a partir de `catalog.json` — não os copie para dentro do arquivo de tópico.

```json
{
  "id": "water",
  "mode": "now",                     // "now" = necessidade urgente, "learn" = trilha de estudo mais longa
  "title": "Obter água potável segura",
  "short": "Tratar, armazenar e encontrar água",
  "intro": "Uma ou duas frases diretas com suas próprias palavras. Descreva em que esta seção ajuda; não dê procedimentos passo a passo aqui.",
  "keywords": ["water", "boil", "bleach", "purify", "água", "ferver", "agua sanitaria", "potável"],
  "choices": [
    {
      "id": "unsafe",
      "label": "Faltou água da rede ou ela pode estar contaminada",
      "hint": "Aviso de fervura, enchente, enxurrada, rompimento de adutora",
      "read": [
        {"doc": "<catalog id>", "page": 9,
         "label": "Título curto orientado à ação do que a página resolve",
         "note": "O que o leitor encontrará nessa página, em até ~30 palavras, descrevendo (sem prescrever)."}
      ]
    }
  ],
  "limits": [
    {"text": "Paráfrase curta e fiel de um limite, alerta ou critério de quando buscar socorro extraído da fonte.",
     "doc": "<catalog id>", "page": 12}
  ],
  "prepare": [ {"doc": "...", "page": 21, "label": "...", "note": "..."} ],
  "learn":   [ {"doc": "...", "label": "...", "note": "..."},
               {"zim": "zim/<arquivo>.zim/<Caminho_do_artigo>", "title": "Title original no ZIM", "label": "...", "note": "..."} ],
  "route": [
    {"title": "Etapa 1: ...", "goal": "Objetivo da etapa em linguagem simples",
     "read": [ {"doc": "...", "page": 3, "label": "...", "note": "..."} ]}
  ],
  "related": ["sanitation", "food"]
}
```

## Regras

- Todo `doc` precisa ser um identificador real do catálogo (nunca um id `metadata-video-*`). `page` é a página do *arquivo* PDF (começando em 1), como usada por `tools/libq.py page`; omita em referências HTML, vídeos ou documentos inteiros. Verifique cada página lendo-a antes de citar.
- Para vídeos, use o próprio id de vídeo (`video-...`). Dê preferência a vídeos com legendas/transcrição e de instituições confiáveis.
- `label`/`note`/`intro`/`hint` são descrições em linguagem simples pensadas para um leigo sob estresse. Podem descrever o que a página contém, mas não devem inventar passos, doses, quantidades ou recomendações que não constem da fonte ou de notas regulatórias explícitas da adaptação brasileira.
- `limits` deve ser rastreável à página citada. Parafraseie com fidelidade; mantenha qualquer citação literal curta (abaixo de 15 palavras).
- Itens médicos, químicos (água sanitária/hipoclorito, combustíveis, defensivos), elétricos e de gás: priorize fontes atuais de referência internacional/técnica (OMS/WHO, CDC, EPA, FEMA, Cruz Vermelha, Hesperian, MSF, USDA, extensão rural) acompanhadas, quando aplicável na adaptação brasileira, dos equivalentes e serviços nacionais (SUS, Ministério da Saúde, Anvisa, Defesa Civil 199, Bombeiros 193, SAMU 192, CVV 188, Disque-Intoxicação 0800-722-6001, Embrapa, ABNT). Indique em `note` se uma fonte for antiga (ex.: defesa civil da década de 1980) ou voltada a profissionais de saúde ou socorristas treinados.
- Prefira menos itens, porém melhores: 1–4 leituras por opção em `choices`, 3–8 em `prepare`, 4–10 em `learn`.
- Em forks traduzidos, preserve sempre `id`, `mode`, `doc`, `page`, `zim`, `related` e mantenha as palavras-chave em inglês em `keywords` junto às entradas em português (com e sem acento).
