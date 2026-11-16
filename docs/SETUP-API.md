# Configuração inicial e gestão de pacotes: contrato compartilhado (`/api/setup/*`)

Um download por computador: aplicativo macOS, instalador Windows (`Setup.exe`) ou pacote Ubuntu (`.deb`). Ao abrir pela primeira vez sem encontrar nenhuma biblioteca, o **Último Livro** (fork brasileiro do **Lastbook**, <https://github.com/Immortal-Protocols/lastbook> / <https://lastbook.org>) abre a tela de **configuração** em sua própria janela (`web/setup.html`). Ela analisa o hardware do computador, recomenda um tamanho de biblioteca (*Small*, *Medium* ou *All*) e informa se a IA local opcional cabe na memória, baixando, validando, desempacotando e ativando tudo em uma etapa. A mesma tela também pode ser reaberta pelo aplicativo (*Biblioteca → Biblioteca e IA local*) para atualizar, instalar IA, trocar mapa estadual ou reparar arquivos.

## Princípios arquiteturais mantidos do projeto original (Lastbook)

- **Única saída para a rede:** o módulo `engine/setup/download.py` é o único código do aplicativo autorizado a acessar a internet, e somente quando a pessoa inicia ou retoma um download. Usa apenas HTTPS na porta 443 para hosts em `ALLOWED_HOSTS`, sem proxy do sistema, seguindo redirecionamentos apenas para outros hosts permitidos. Todo o restante do app bloqueia cargas web externas, não possui telemetria nem verificações em segundo plano.
- **Sem piso arbitrário de memória:** a IA local é oferecida quando a medição real ou estimativa (`llm_local.judge`) indica que modelo + contexto cabem com folga de reserva (`2,5 GiB`, ~18 GB totais). Caso não caiba, a interface explica o motivo em linguagem clara em português.
- **Uma biblioteca funcional nunca é quebrada:** dados novos são baixados e desempacotados ao lado da instalação antiga, validados e ativados em uma única operação atômica de renomeação (`LastbookData.old-*`). Falhas em qualquer ponto preservam intacta a biblioteca anterior.

## Organização dos módulos

| Parte | Arquivos principais |
|---|---|
| Baixador, validações, desempacotamento, troca atômica, hardware, manifesto e API `/api/setup/*` | `engine/setup/` (`api.py`, `download.py`, `hardware.py`, `install.py`, `manifest.py`, `roots.pem`), `packaging/release_manifest.py`, modo setup em `app/main.py` |
| Interface de configuração | `web/setup.html`, `web/setup.js`, `web/setup.css` (e link na aba Biblioteca de `web/app.js`) |
| Construção de pacotes e mapas estaduais | `packaging/build_packs.py`, `packaging/state_maps.py`, `packaging/address_indexes.py`, `derived/packs/pack-spec.json` |
| Domínio de download e manifesto no upstream | `downloads.lastbook.org` (`engine/setup/download.py`, `engine/setup/manifest.py`, `engine/update.py`) |
| Executores de IA local e empacotamento por SO | `packaging/llm/*`, `packaging/build_app_*.sh`, `packaging/scan_*`, `llm_local.py`, `assistant.py`, `server.py` |

## O manifesto (`manifest-v1.json`)

O aplicativo pode trazer uma cópia embutida no build (`setup/manifest-v1.json`, gerada por `packaging/release_manifest.py`) e também pode consultar `https://downloads.lastbook.org/manifest-v1.json` (um único `GET` quando o usuário abre a tela de setup online). O manifesto remoto só é aceito se for JSON válido com `"version": 1` e todas as URLs em hosts permitidos.

```json
{
  "version": 1,
  "published": "2026-11-12",
  "packs": [
    {"id": "small", "title": "Small", "summary": "…uma frase simples…", "records": 315,
     "installed_bytes": 8236931672, "available": true,
     "files": [{"name": "Lastbook-Small.zip", "url": "https://downloads.lastbook.org/1.0.0/Lastbook-Small.zip",
                "size": 8236931672, "sha256": "…", "kind": "zip"}]}
  ],
  "models": [
    {"id": "gemma-4-26b-a4b", "title": "Gemma 4 26B A4B", "file": "gemma-4-26B-A4B-it-UD-Q4_K_M.gguf",
     "url": "https://huggingface.co/unsloth/gemma-4-26B-A4B-it-GGUF/resolve/c099eb48e663fd284577b04978a94ffccb261841/gemma-4-26B-A4B-it-UD-Q4_K_M.gguf?download=true",
     "size": 16947541728, "sha256": "f2c28b3dc4776931ac6f879e11f203dec637ea0f14267a86ec8f6165f63f293f",
     "memory_bytes": 19027384256, "available": true}
  ]
}
```

- `installed_bytes` é o tamanho medido já desempacotado. Um pacote com `"available": false` aparece indisponível e não pode ser escolhido.
- `ALLOWED_HOSTS` em `engine/setup/download.py` lista explicitamente os hosts permitidos (`downloads.lastbook.org`, buckets R2 configurados, `huggingface.co` e CDNs de redirecionamento de modelos do Hugging Face).

## Onde os arquivos ficam no disco

- A pasta da biblioteca mantém o nome interno **`LastbookData`** (`library-data/`, `derived/`) por compatibilidade com pacotes, instaladores e testes. Local padrão: `~/Library/Application Support/Lastbook/LastbookData` no macOS, pasta de dados locais/Documents no Windows e `~/.local/share/Lastbook/LastbookData` no Linux (ou outra escolhida pelo usuário; se o caminho do Windows exceder o limite de profundidade, `default_choice()` em `app/main.py` cria uma pasta curta protegida em `<drive>:\Lastbook`).
- Área temporária de trabalho: `<pasta-pai>/LastbookData.setup/`, com `downloads/` (`.part` e metadados `.json` com URL, tamanho, SHA-256, bytes baixados e ETag) e `unpack/`.
- O modelo de IA vai para `LastbookData/models/<arquivo>`. Após validar o SHA-256 na instalação, o setup chama `llm_local.mark_checked(path)` para evitar reler ~17 GB ao iniciar o chat.
- Espaço exigido = tamanho do download + tamanho desempacotado + margem de reserva de 2 GB no disco de destino. O `.zip` é apagado após ser desempacotado e verificado.
- Arquivos já presentes no computador (`Lastbook-*.zip`, `Lastbook-Map-*.zip`, modelo `.gguf` ou `LastbookData` existente em Downloads/Documentos/Desktop ou escolhidos manualmente) são reconhecidos e validados via SHA-256 antes do uso.

## Interface da API local: `/api/setup/*`

Tráfego em JSON pela ponte em memória (ou apenas loopback no modo servidor; dispositivos externos na rede local recebem HTTP 403). Requisições `POST` exigem a chave de sessão no app desktop.

| Requisição | Resposta / comportamento |
|---|---|
| `GET /api/setup/state` | `{mode: "first-run" ou "manage", hardware, manifest: {source: "bundled" ou "fetched", packs, models, maps, address_indexes}, current: {folder, pack, model, map, address_indexes, ...} ou null, found: [...], recommend: {pack, ai, why, folder, need_bytes, map_need_bytes}, job}` |
| `POST /api/setup/start` `{pack, ai, map?, addresses?, folder?}` | Inicia `job` de instalação/atualização, ou `{error, need_bytes, free_bytes}` |
| `POST /api/setup/start` `{repair: true, ai}` | Modo manutenção: confere cada arquivo contra `pack-manifest.tsv` e SHA-256 do modelo e baixa novamente apenas o que estiver corrompido ou ausente |
| `GET /api/setup/job` | Estado atual de `job` |
| `POST /api/setup/pause`, `/resume`, `/cancel`, `/retry` | Controla o `job` em andamento ou com falha |
| `POST /api/setup/use` `{path}` | Verifica e utiliza pacote, mapa, índice de endereços, modelo ou pasta `LastbookData` já existente |
| `POST /api/setup/finish` | Grava a pasta escolhida em `settings.json` e reinicia/reabre o aplicativo na biblioteca pronta |
| `POST /api/setup/pick` `{files?}` | Abre seletor nativo e retorna `{path, free_bytes, disk}` ou `{path: null, cancelled: true}` |
| `POST /api/setup/delete-old` `{path}` | Remove uma cópia antiga `LastbookData.old-*` movida anteriormente pelo setup |
| `POST /api/setup/remove-ai` | Modo manutenção: remove `LastbookData/models/<arquivo>` mantendo a biblioteca |

Códigos de erro padronizados: `busy`, `not_done`, `no_space`, `network`, `checksum`, `unpack`, `activate`, `cancelled`, `found_mismatch`, `unavailable`, `nothing`, `folder`.
Os estados do trabalho em `job.json` (armazenado na pasta de configurações do aplicativo, nunca dentro de `LastbookData.setup` por segurança) progridem em: `waiting` → `downloading` → `verifying` → `unpacking` → `activating` → `done` (ou `paused` / `failed`).

## Mapas estaduais e índices de endereços

O setup permite instalar um pacote de biblioteca junto ou separadamente de um **mapa estadual** (`maps`) e de um **índice de endereços** (`address_indexes`, por UF de 2 letras `[A-Z]{2}` — contemplando os estados dos EUA do upstream e as 27 UFs brasileiras adicionadas neste fork em `packaging/state_maps.py`).

- Pacotes de mapa contêm apenas arquivos autorizados sob `derived/geo/*.sqlite`, `derived/geo/national-status.json`, `derived/geo/socal-cells.json`, `library-data/geography/resources/atlas.sqlite` e `map-set.json` identificando o código do mapa (`base`, `us`, `br` ou código de UF de 2 letras).
- Na tela de setup (`web/setup.js`), o usuário escolhe o país/estado (UF) manualmente; nenhum componente faz geolocalização automática.
- Pacotes `base`, `us` e `br` encaminham a escolha padrão de endereços sem exigir um código estadual específico em `engine/setup/api.py`.
