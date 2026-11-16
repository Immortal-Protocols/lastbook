# Como o mapa offline é montado

Guia técnico para quem deseja aprimorar o mapa do **Último Livro** (fork brasileiro do **Lastbook**, <https://github.com/Immortal-Protocols/lastbook> / <https://lastbook.org>): adicionar novos tipos de locais, exibir categorias já existentes nos dados ou ampliar a cobertura territorial. Descreve quais arquivos o aplicativo lê, qual ferramenta constrói cada banco, o que mudou na versão brasileira e onde ficam eventuais lacunas.

O mapa segue as mesmas regras do restante do aplicativo (veja [CONTRIBUTING.md](../CONTRIBUTING.md)). Em execução, o aplicativo lê apenas arquivos locais no computador e nunca consulta a rede para obter tiles, locais ou endereços (também bloqueia `navigator.geolocation` por privacidade). Já as ferramentas de construção em `tools/` rodam em uma máquina de build/curadoria e não são empacotadas no aplicativo final.

## O que o aplicativo lê

Um conjunto de mapas fica na pasta de dados (`LastbookData`). O arquivo `map-set.json` na raiz lista os arquivos e tamanhos conferidos na instalação.

| Arquivo | Tabelas | Conteúdo | Lido por |
|---|---|---|---|
| `derived/geo/national.sqlite` | `feat`, `feat_idx`, `poi`, `meta` | Vias, corpos d'água, formas territoriais e pinos de locais | `server.py` (`national_mapdb`) |
| `derived/geo/map.sqlite` | as mesmas quatro | Mapa detalhado local (no upstream: Sul da Califórnia; em builds brasileiros: recorte regional configurado) | `server.py` (`mapdb`) |
| `derived/geo/water.sqlite` | `resource`, `spatial`, `feat`, `feat_idx` | Barragens, reservatórios, lagos e açudes | `server.py` |
| `derived/geo/crops.sqlite` | `resource`, `spatial`, `tile` | Cultivos e cobertura agrícola | `server.py` |
| `derived/geo/terrain.sqlite` | `tile` | Tiles de elevação para relevo, curvas de nível e visão 3D | `server.py` |
| `derived/geo/buildings.sqlite` | `bldg` | Contornos de edificações | `server.py` |
| `derived/geo/places.sqlite` | `place`, `place_fts` | Buscador de localidades: municípios/bairros, CEPs/códigos postais e locais nomeados | `server.py` (`/api/places`) |
| `library-data/geography/resources/atlas.sqlite` | `resource`, `spatial` | Registros de recursos naturais (no pacote exemplo dos EUA do upstream, minerais e camadas da Califórnia) | `server.py` |
| `derived/geo/addresses/` | um índice SQLite por estado/UF | Endereços com numeração e CEP para busca offline | `engine/address_search.py` |

Dois tipos de tabelas guardam os pontos que a pessoa pode tocar no mapa:

- `poi(id, cls, name, lon, lat)`: ponto categorizado por classe OpenStreetMap, como `hospital` ou `fuel`.
- `resource(id, source_id, kind, name, lat, lon, detail, source, origin)` com índice `spatial`: registro temático com classe, detalhe e nome da fonte.

## Como um tipo de local aparece no mapa

1. Existe uma linha com `poi.cls` ou `resource.kind` em um dos arquivos SQLite acima.
2. Essa classe é mapeada em uma camada em `web/map.js` (`LAYERS`: `id`, `label`, `symbol`, `colour`, `classes`, `group`).
3. O servidor informa quais classes existem de fato no conjunto instalado (`map_contents` em `server.py`), e a interface mostra somente as camadas que possuem registros.

Uma classe presente nos dados mas sem entrada em `LAYERS` não aparece no painel de camadas (embora `HELP` em `server.py` já traduza diversos nomes amigáveis como Escola, Dentista, Veterinário, Casa de repouso, Correios).

### Classes frequentemente presentes no OSM que não têm camada dedicada

Nos pacotes gerados por `tools/build_map.py` (`POI_KEEP`), há categorias como `school`, `fountain`, `dentist`, `post_office`, `car_repair`, `park`, `veterinary`, `college`, `university`, `garden_centre`, `nursing_home` e `water_works`. Para exibi-las, basta adicionar a entrada correspondente em `LAYERS` de `web/map.js` mantendo justificativa clara de utilidade em emergências.

## O que constrói cada arquivo

| Arquivo | Ferramenta | Origem no projeto original (upstream EUA) / observação BR |
|---|---|---|
| `map.sqlite` | `tools/build_map.py` + `tools/build_coast.py` | Extrato regional do OpenStreetMap (ODbL) — compatível diretamente com extratos `.osm.pbf`/`.gpkg` do Brasil (Geofabrik South America / Brazil). |
| `water.sqlite` | `tools/build_water.py` | Upstream: USACE (barragens) e USGS NHD. Para o Brasil, usa dados de água do OSM ou adaptações equivalentes (ex.: ANA/IBGE). |
| `crops.sqlite` | `tools/build_crops.py` | Upstream: USDA Cropland Data Layer (EUA). |
| `terrain.sqlite` | `tools/build_terrain.py` | Modelos digitais de elevação (upstream: USGS 3DEP; globalmente aplicável com fontes SRTM/Copernicus adaptadas ao script). |
| `buildings.sqlite` | `tools/build_buildings.py` + `tools/build_osm_heights.py` | Pegadas de edificações Microsoft Building Footprints (ODbL) e alturas OpenStreetMap (há cobertura global incluindo o Brasil). |
| `places.sqlite` | `tools/build_places.py` | Upstream: USGS GNIS, U.S. Census + OpenStreetMap local. Para o Brasil, popula nomes/POIs de `map.sqlite` e requer adaptador específico caso utilize gazetteers IBGE/Correios. |
| Índices de endereço | `tools/build_addresses.py` + `packaging/address_indexes.py` | Endereços do **Overture Maps**. Adaptado neste fork brasileiro para `--bbox br` como padrão e CEPs de 8 dígitos (`engine/address_search.py`). |
| Mapa estadual (`<UF>`) ou nacional (`br`) | `packaging/build_packs.py map <UF\|br>`, listado em `packaging/state_maps.py` | Mapa-base mais recorte espacial pelos polígonos oficiais em `web/geographic-context.json`. |

Leia sempre o cabeçalho de cada script em `tools/` antes de executá-lo: alguns trabalham com arquivos brutos de centenas de gigabytes.

### O que não faz parte deste repositório

- **Construtor de `national.sqlite` e `atlas.sqlite`:** as ferramentas de empacotamento copiam e recortam de bancos `national.sqlite` e `atlas.sqlite` já preparados na máquina de build do projeto original.
- **Mesclagem de `derived/geo/places-*.sqlite`:** os scripts `tools/build_places_civic.py`, `_usgs.py`, `_overture.py`, `_atp.py`, `_fsq.py`, `_fuel.py` e `_snap.py` são coletores auxiliares herdados do projeto original cujos bancos intermediários eram unidos fora deste repositório (`game/serve.py` no ambiente original do autor).

## Adaptações implementadas para o Brasil neste fork

No projeto original (**Lastbook**), o mapa e os endereços eram exclusivamente focados nos Estados Unidos (UFs dos EUA, códigos ZIP de 5 dígitos e enquadramento no Sul da Califórnia/EUA). Neste fork brasileiro (**Último Livro**):

1. **`web/geographic-context.json`:** passou a incluir os polígonos oficiais das 27 unidades federativas do Brasil (`AC` a `TO`, dados IBGE) além do contexto hidrográfico original.
2. **`web/map.js`:** centralização inicial no Brasil, conversão da escala e medições para sistema métrico (`m`, `km`), busca com suporte a CEP de 8 dígitos (`12345-678` ou `12345678`) e toda a interface traduzida para português do Brasil.
3. **`engine/address_search.py`:** normalização sem acentos (`fold_txt`), tipos de logradouro brasileiros (*Rua*, *Avenida*, *Alameda*, *Travessa*, *Estrada*, *Rodovia*, *Praça*, *Largo*, etc.), todas as 27 UFs e suporte completo a endereços e CEPs do Brasil mantido em paralelo à compatibilidade com testes legados dos EUA.
4. **`tools/build_addresses.py`, `packaging/state_maps.py` e `packaging/build_packs.py`:** inclusão das 27 UFs brasileiras, `--bbox br` como padrão na extração de endereços, cálculo automático de bounding box estadual em `state_box()` via `web/geographic-context.json` e suporte a `map br`.
5. **`server.py`:** limites geográficos para o Brasil em `/api/places`, tradução de categorias de ajuda (`HELP`) e resultados em unidades métricas (`km`, `ha`, `m³`).

> Nota sobre dados binários externos: para gerar novos pacotes `.sqlite` brasileiros prontos para uso final, ainda é necessário executar os scripts de build com extratos OpenStreetMap/Overture do Brasil; caso utilize dados nacionais do projeto original, as camadas geográficas detalhadas dos EUA continuarão usando os rótulos originais correspondentes àquele conjunto de dados.

## Verificação de alterações no mapa

- Alterações visuais em camadas de `web/map.js`: anexe capturas de tela em modo claro e escuro no PR.
- Alterações nas ferramentas de empacotamento/mapa: `packaging/scan_pack.py` define a lista permitida sob `derived/geo/` (`GEO_FILES`) e `packaging/test_pack_tools.py` valida os pacotes gerados.
- Nenhuma modificação pode abrir conexões de rede no aplicativo em execução; novos dados entram sempre via ferramenta de geração offline e arquivo empacotado.
