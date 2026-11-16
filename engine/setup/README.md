# `engine/setup`: configuração inicial e manutenção (lado do motor)

O contrato da API está documentado em [docs/SETUP-API.md](../../docs/SETUP-API.md). Este pacote implementa toda a lógica de configuração inicial e gestão da biblioteca do **Último Livro** (fork brasileiro do **Lastbook**).

| Arquivo | O que faz |
|---|---|
| `download.py` | Único módulo do aplicativo autorizado a abrir conexões de rede. Faz HTTPS na porta 443 apenas para `ALLOWED_HOSTS` (e `*.hf.co`), sem usar proxy do sistema (usa `http.client`). Redirecionamentos só são seguidos para endereços permitidos. Suporta retomada com HTTP `Range`, comparação direta de `ETag` (para buckets R2 que ignoram `If-Range`) e cálculo de SHA-256 em streaming durante o download. |
| `roots.pem` | Único conjunto de certificados raiz aceitos pelo baixador (11 raízes extraídas do bundle da Mozilla cobrindo os hosts permitidos). O repositório de certificados do sistema nunca é usado. Reconstrua com `packaging/setup_roots.py <certifi cacert.pem>`. As verificações de empacotamento exigem esse arquivo. |
| `manifest.py` | Carrega `setup/manifest-v1.json` empacotado e opcionalmente consulta uma única vez `https://downloads.lastbook.org/manifest-v1.json` ao abrir o setup online, aceitando a cópia remota apenas após validação estrita de esquema e URLs permitidas. Aceita índices estaduais com sigla de 2 letras (`[A-Z]{2}`). |
| `hardware.py` | Lê sistema operacional, arquitetura, RAM, memória unificada, GPUs/VRAM (DXGI via `ctypes` no Windows; `sysctl` e `/proc`/`/sys` no macOS e Linux) e espaço livre em disco (incluindo fallback via `/Volumes` no macOS quando PyObjC não está presente). Estima ou mede (`lastbook-llm --measure` + `llm_local.judge`) se o modelo de IA cabe. |
| `install.py` | Valida arquivos `.zip` antes de gravar qualquer byte no disco: proteção contra zip-slip, caminhos absolutos, links simbólicos, colisões de caixa, criptografia e limite de tamanho frente a `installed_bytes`. Desempacota permitindo retomada, executa troca atômica com backup `.old-*` e reverte automaticamente se a nova biblioteca falhar ao abrir. |
| `api.py` | Implementa `/api/setup/*`, gerencia a fila de tarefas (`job.json`, pausa, retomada, cancelamento e nova tentativa), detecta pacotes/mapas/modelos já presentes no computador, calcula recomendações e fornece `SetupServer` para a ponte quando ainda não há biblioteca instalada. |

## Como funciona

- **Modo setup (primeira execução):** `app/main.py` não encontra biblioteca existente e abre a janela em `SetupServer` pela ponte em memória, sem abrir portas. A página `web/setup.html` é servida em `/`. Downloads vão para `<pasta-pai>/LastbookData.setup/downloads/` e são desempacotados em `.../unpack/LastbookData`. Ao concluir, grava `pending.json`, salva a pasta alvo em `settings.json` e reinicia o aplicativo (`execv` no macOS/Linux ou novo processo no Windows). Na inicialização seguinte, `api.startup()` conclui a troca antes de abrir qualquer arquivo da biblioteca.
- **Modo manutenção (biblioteca já instalada):** `server.py` encaminha `/api/setup/` para `api.handle()`. A página é acessada em `/ui/setup.html`. Upgrades e trocas de mapa estadual são preparados da mesma forma e aplicados ao reiniciar. A inclusão ou remoção apenas da IA local é feita diretamente na biblioteca aberta.
- Somente a própria máquina local recebe respostas (`403` para clientes externos na rede local).

## Testes do setup

Os testes usam um servidor HTTPS local em memória definido apenas no arquivo de testes (`app/tests/test_setup.py`), simulando quedas de conexão, bytes corrompidos, mudança de ETag, servidores que ignoram `Range`, redirecionamentos inválidos, interrupção no meio da extração e limites de disco:

```bash
python3 -B -m unittest app.tests.test_setup -v
```

Caso queira exercitar também o cenário de disco cheio em macOS (`hdiutil` com imagem de 3 MB):

```bash
LASTBOOK_FULL_DISK=1 python3 -B -m unittest app.tests.test_setup.FullDisk -v
```
