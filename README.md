# Último Livro (Fork Brasileiro do Lastbook)

**Último Livro** é uma biblioteca offline de sobrevivência, saúde, infraestrutura e reconstrução para macOS, Windows e Linux, adaptada para o Brasil (português do Brasil, sistema métrico, padrões técnicos/regulatórios nacionais, CEPs de 8 dígitos e todas as 27 UFs). Ele reúne manuais, vídeos, enciclopédias, mapa offline e guias práticos curtos em um único computador. Depois de configurado, funciona totalmente offline.

A barra lateral do aplicativo abre **Vídeos**, **Mapa**, **Chat**, **Enciclopédias**, **Tradutor**, **Cofre**, **Diagnóstico** e **Biblioteca e IA** (além das rotas diretas para **Guias**, **Biblioteca**, **Buscar** e **Salvos**). O Chat responde perguntas usando os documentos e enciclopédias da biblioteca e cita as fontes com links diretos para as páginas.

Projeto original (upstream): **Lastbook** — repositório <https://github.com/Immortal-Protocols/lastbook>, site oficial <https://lastbook.org>, contato `hello@lastbook.org`.
Inspiração e referência adicional de módulos offline em português: **refugiOS** — repositório <https://github.com/Ganso/refugiOS>.

> O código e a documentação originais do Lastbook são licenciados sob a [Licença MIT](LICENSE).
> Contribuições são bem-vindas. Consulte [CONTRIBUTING.md](CONTRIBUTING.md) e [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## O que o projeto faz

- **Guias práticos primeiro (`content/topics/`).** Roteiros curtos e diretos para emergências e necessidades essenciais, apontando para páginas reais da biblioteca com indicação de página, além das lacunas mapeadas pelos curadores (`content/gaps.json`). Adaptado ao contexto brasileiro (SUS, SAMU 192, Bombeiros 193, Defesa Civil 199 / SMS 40199, CVV 188, Disque-Intoxicação 0800-722-6001, padrões Anvisa de hipoclorito, rede elétrica 127 V / 220 V em 60 Hz, normas ABNT, Anatel/PX/RENER e estações do Hemisfério Sul).
- **Biblioteca completa e Enciclopédias em Português (Kiwix / `.zim`, inspirado no [refugiOS](https://github.com/Ganso/refugiOS)).** Manuais e PDFs (renderizados como imagens no visualizador seguro), vídeos com transcrição e catálogo integrado de 10 coleções `.zim` em português em `engine/kiwix_br.py` (**WikiMed PT**, **Wikipédia PT** em 4 faixas de tamanho, **iFixit PT**, **Wikibooks PT**, **Wikivoyage PT**, **Wikcionário PT** e **Simulações PhET PT**), com download verificado por SHA-256 no Gerenciador e busca integrada tanto na aba **Enciclopédias** quanto pelo assistente de IA local (`assistant.py`).
- **Mapa offline do Brasil e das 27 UFs via OpenStreetMap (`engine/osm_br.py`).** Mapa-base mundial e do Brasil (`web/geographic-context.json` com os polígonos das 27 unidades federativas pelo IBGE) + download direto por estado (UF) pelo OpenStreetMap (`openstreetmap.org`) com cache local de tiles raster (`/api/map/osm/<z>/<x>/<y>.png`), geração de `map.sqlite` / `places.sqlite` e busca de ruas, municípios e CEPs de 8 dígitos (`engine/address_search.py` + BrasilAPI). A pessoa escolhe o estado na configuração; o aplicativo nunca solicita ou detecta localização automática.
- **IA local opcional em 4 tamanhos, Seletor Inteligente e modo "Só resultado".** Responde em português usando os documentos e enciclopédias locais, com citação de fontes, por meio dos modelos em `llm_local.py`: **Gemma 4 26B A4B** (~17 GB, 24+ GB RAM), **Gemma 4 E4B** (~5 GB, 12–16 GB RAM), **Gemma 4 E2B** (~3,1 GB, 8 GB RAM) e **Qwen 3.5 0.8B** (~508 MB, 4 GB RAM, inspirado no **refugiOS**). Inclui seletor no Chat/Gerenciador para alternar entre modelos instalados (`select_model`) e botão **Só resultado** ligado por padrão para ocultar etapas de raciocínio e planejamento em texto puro do modelo.
- **Cofre Criptografado de Emergência (`engine/vault.py`, inspirado no [refugiOS](https://github.com/Ganso/refugiOS)).** Armazenamento portátil protegido por senha forte (`PBKDF2-HMAC-SHA256` com 250.000 iterações + cifra de fluxo `BLAKE2b` + autenticação `HMAC-SHA256`) em `LastbookData/derived/vault/` para guardar documentos pessoais (CPF, RG, CNH), ficha médica e alergias, contatos da família, senhas/anotações e anexos cifrados.
- **Tradutor Offline Integrado (`engine/translator.py`, inspirado no [refugiOS](https://github.com/Ganso/refugiOS)).** Botão **`Traduzir (PT)`** na leitura de qualquer manual (`#/read/...`) com cache local em `derived/translations/`, além da aba **Tradutor** (`#/translate`) para tradução livre offline via IA local e consulta a um guia rápido de frases de emergência (Inglês / Espanhol / Português do Brasil) que funciona mesmo sem modelo de IA instalado.
- **Diagnóstico Completo da Instalação (`engine/checker.py`, inspirado no `refugios-check.py` do [refugiOS](https://github.com/Ganso/refugiOS)).** Aba **Diagnóstico** (`#/check`) com verificação rápida ou completa (recomputando SHA-256) da biblioteca base, mapas estaduais, enciclopédias `.zim`, modelos `.gguf` e memória compatível, cofres criptografados e espaço livre em disco, gravando relatório em `derived/logs/relatorio-verificacao.txt`.
- **Configuração em um download / pasta local.** Na primeira execução, o assistente permite baixar um pacote ou selecionar uma pasta `LastbookData` (ou arquivo `.zip`) já existente no computador.
- **Verificação manual de atualizações.** A página Sobre traz o botão de verificar atualizações (`engine/update.py`, `web/update.js`). Nada é baixado ou instalado automaticamente.

## Privacidade e uso de rede

- **Nenhuma porta de rede aberta no app desktop.** A janela e o motor conversam por uma ponte em memória (`app/bridge.py`): `WKURLSchemeHandler` no macOS (`app/shell_macos.py`), `WebResourceRequested` no WebView2 do Windows (`app/shell_windows.py`) e `URISchemeRequest` no WebKitGTK do Linux (`app/shell_linux.py`). O executor de IA local conversa via JSON lines na entrada/saída padrão, também sem abrir sockets.
- **Uso restrito da rede, apenas quando iniciado pelo usuário.** O baixador de configuração (`engine/setup/`) e o verificador de atualizações (`engine/update.py`) passam exclusivamente por `engine/setup/download.py`: apenas HTTPS na porta 443, para hosts na lista permitida (`downloads.lastbook.org`, `huggingface.co` / `*.hf.co`, `www.openstreetmap.org`, `nominatim.openstreetmap.org`, `brasilapi.com.br` e espelhos oficiais Kiwix/Wikimedia para os `.zim`), sem proxy do sistema. Tiles de mapa do OpenStreetMap são buscados apenas quando a camada OSM é exibida online e ficam armazenados em cache para uso posterior offline.
- **Raízes TLS fixadas e verificação de integridade.** Confia apenas nos certificados em `engine/setup/roots.pem` (gate validado em `packaging/check_tls_roots.py`) e valida SHA-256 de cada arquivo antes do uso. Os pacotes ZIP são validados contra caminhos inválidos, links e tamanhos excessivos antes da extração.
- **Sem telemetria.** As janelas bloqueiam carregamentos externos (`https?://` em `web/` é proibido pelos testes e scans de empacotamento), não há conta de usuário nem timers em segundo plano acessando a internet.

Consulte o contrato de configuração em [docs/SETUP-API.md](docs/SETUP-API.md) e [engine/setup/README.md](engine/setup/README.md).

## Estrutura do repositório

| Caminho | Descrição |
|---|---|
| `app/` | Aplicativo desktop: ponto de entrada (`main.py`), ponte sem porta (`bridge.py`), shells macOS/Windows/Linux e suíte de testes (`app/tests/`). |
| `engine/` | Descoberta da pasta de dados (`paths.py`), catálogo/ZIM/busca FTS5 (`library.py`), sanitização de páginas (`saved_pages.py`), busca offline de endereços e CEP (`address_search.py`), mapas estaduais OSM (`osm_br.py`), catálogo Kiwix em português (`kiwix_br.py`), cofre criptografado (`vault.py`), tradutor offline (`translator.py`), diagnóstico de integridade (`checker.py`), atualizações (`update.py`) e assistente de setup (`engine/setup/`). `engine/vendor-macos/` traz o `pypdfium2` para macOS. |
| `server.py`, `assistant.py`, `retrieval.py`, `llm_local.py` | Motor principal: servidor HTTP/API local, assistente e validação de citações, busca híbrida em PT-BR e controle da IA local. |
| `web/` | Interface web em HTML, CSS e JavaScript puros, sem etapa de build e sem recursos externos (`index.html`, `app.js`, `map.js`, `chat.js`, `setup.js`, `words.js`). |
| `content/` | Guias temáticos em PT-BR (`topics/*.json`) e lacunas documentadas (`gaps.json`). Esquema em `content/SCHEMA.md`. |
| `packaging/` | Scripts de empacotamento para macOS, Windows e Linux, instalador Windows (`setup_stub/`), ícones, construtores de pacotes e mapas estaduais (`build_packs.py`, `state_maps.py`, `address_indexes.py`), validação de pacotes e runner de IA local (`packaging/llm/`). |
| `derived/packs/pack-spec.json` | Especificação dos pacotes (`small`, `medium`, `all`, complementos) e mapas estaduais. |
| `tools/` | Ferramentas para gerar mapas, endereços brasileiros (`build_addresses.py --bbox br`) e pontos de interesse, além de utilitários de curadoria (`libq.py`, `validate_topics.py`). |
| `docs/` | Documentação técnica (`SETUP-API.md`, `MAPS.md`, `LIBRARY-SERVER.md`). |

## Executar a partir do código-fonte

É necessário Python 3.11+ e uma **pasta de dados** (`LastbookData`) contendo `library-data/catalog.json`. Caso ainda não tenha uma pasta de dados, o aplicativo abre automaticamente a tela de configuração na primeira execução.

```bash
python3 -m venv .venv
.venv/bin/pip install -r packaging/requirements_macos.txt   # no Windows: packaging/requirements_app.txt
.venv/bin/python app/main.py --data /caminho/para/LastbookData
```

Sem `--data`, o aplicativo verifica a variável `LASTBOOK_DATA`, a última pasta escolhida nas configurações e a pasta de dados padrão do sistema.

Para executar no **modo servidor web** (útil em Linux, Raspberry Pi ou para compartilhar com celulares na mesma rede Wi-Fi offline):

```bash
LASTBOOK_DATA=/caminho/para/LastbookData python3 server.py   # acesse http://127.0.0.1:8890/
```

Consulte [docs/LIBRARY-SERVER.md](docs/LIBRARY-SERVER.md).

## Mapas, endereços e pacotes do Brasil

Os arquivos binários pesados (`library-data/`, modelos `.gguf`/`.onnx` e bases `.sqlite` geradas em `derived/geo/`) não ficam versionados neste repositório. Para gerar os recortes e índices voltados ao Brasil a partir dos dados geográficos do OpenStreetMap/Overture:

- **Endereços e CEPs do Brasil:** `tools/build_addresses.py` utiliza `--bbox br` como padrão e aceita CEPs brasileiros de 8 dígitos.
- **Índices por UF (27 estados + DF):** `packaging/state_maps.py` inclui as 27 UFs brasileiras (`AC`..`TO`), e `packaging/address_indexes.py` divide o banco `addresses.sqlite` por UF.
- **Mapas estaduais e nacional (`br`):** `packaging/build_packs.py map <UF|br>` recorta cada unidade federativa usando os polígonos oficiais em `web/geographic-context.json`.

## Compilar os aplicativos

Os builds escrevem em `derived/app-build/` e falham automaticamente se a verificação de empacotamento detectar código de teste, chamadas de rede fora do `downloader`, URLs externas em `web/` ou termos proibidos configurados em `packaging/ship_edits.json`.

**macOS (Apple Silicon):**

```bash
bash packaging/llm/build_llm_macos.sh    # opcional: executor local llama.cpp com Metal
bash packaging/build_app_macos.sh        # gera derived/app-build/mac/<data>/dist/Último Livro.app
```

**Windows (64 bits, no Git Bash):**

```bash
TOOLS='C:\caminho\para\tools' bash packaging/llm/build_llm_windows.sh
PY=/c/caminho/para/python.exe OUT='C:\caminho\para\saida' bash packaging/build_app_windows.sh
PY=/c/caminho/para/python.exe DIST='C:\caminho\para\saida\dist\Lastbook' OUT='C:\caminho\para\saida' bash packaging/build_setup_windows.sh
```

**Linux (Ubuntu 24.04 x86_64):**

```bash
bash packaging/llm/build_llm_linux.sh
bash packaging/linux/build_app_linux.sh
```

## Pacotes, mapas estaduais e IA local

- **Pacotes (`small`, `medium`, `all`):** montados por `packaging/build_packs.py` a partir de `derived/packs/pack-spec.json` e verificados por `packaging/verify_packs.py` e `packaging/scan_pack.py`.
- **IA local (`llm_local.py`):** oferece quatro modelos GGUF com nome, tamanho, SHA-256 e revisão fixados:
  - `gemma-4-26b-a4b`: **Gemma 4 26B A4B** (`gemma-4-26B-A4B-it-UD-Q4_K_M.gguf`, ~17 GB, 24+ GB RAM).
  - `gemma-4-e4b`: **Gemma 4 E4B** (`gemma-4-E4B-it-Q4_K_M.gguf`, ~5 GB, 12–16 GB RAM).
  - `gemma-4-e2b`: **Gemma 4 E2B** (`gemma-4-E2B-it-Q4_K_M.gguf`, ~3,1 GB, 8 GB RAM).
  - `qwen-3.5-0.8b`: **Qwen 3.5 0.8B** (`Qwen3.5-0.8B-Q4_K_M.gguf`, ~508 MB, 4 GB RAM, template ChatML — inspirado no `refugiOS`).
  A configuração só oferece o download quando a memória medida ou estimada do computador comporta o modelo com margem de segurança. O executor `lastbook-llm` (`packaging/llm/lastbook_llm.cpp`) usa Metal no macOS e Vulkan com fallback em CPU no Windows e Linux.
- **Busca por significado:** usa ONNX Runtime no Windows; as compilações macOS utilizam busca por palavras-chave e sinônimos.

## Testes

Execute a suíte completa de testes unitários e de integração em memória:

```bash
python3 -B -m unittest app.tests.test_bridge app.tests.test_setup app.tests.test_data_folder app.tests.test_what_ships app.tests.test_update app.tests.test_address_search app.tests.test_topic_search app.tests.test_validate_topics app.tests.test_libq
```

> Nota: manter `app.tests.test_bridge` primeiro na lista garante que o gancho de verificação de sockets (`test_no_listening_socket_and_no_model`) execute antes do servidor HTTPS local de testes usado por `app.tests.test_setup`. Testes de ZIM em `test_validate_topics` e `test_libq` são ignorados automaticamente caso `libzim` não esteja instalada no ambiente Python local.

`packaging/test_pack_tools.py SAMPLE WORK` valida as ferramentas de empacotamento contra uma amostra real de pacote (`build_packs.py build <pack> --sample N`).

## Projetos de referência e inspiração

- **Lastbook (upstream):** <https://github.com/Immortal-Protocols/lastbook> — base estrutural do aplicativo desktop sem portas, ponte segura, visualizador de manuais, mapas e guias curados.
- **refugiOS:** <https://github.com/Ganso/refugiOS> — referência de arquitetura e UX para resiliência offline multiplataforma e em múltiplos hardware, inspirando diretamente os módulos de enciclopédias Kiwix em português, modelo compacto de 0.8B com seletor inteligente de IA, cofre criptografado para dados familiares, tradutor offline e diagnóstico de integridade com relatório.

## Contribuição e licença

Consulte [CONTRIBUTING.md](CONTRIBUTING.md) e [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md). O código e a documentação originais usam a [Licença MIT](LICENSE). Softwares, modelos, vídeos e documentos de terceiros mantêm suas licenças próprias listadas em [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
