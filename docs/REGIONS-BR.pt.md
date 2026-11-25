# Mapas detalhados para o Brasil: uma proposta

Esta é uma proposta para discussão, não uma decisão. Ela responde, para o Brasil, as perguntas que [MAPS.md](MAPS.md)
faz antes de a cobertura poder ir além dos Estados Unidos: qual fonte aberta substitui cada lista federal, sob qual
licença, o que é um "estado" ali e como os endereços são escritos. Segue a estrutura de
[REGIONS-MX.md](REGIONS-MX.md) e [REGIONS-AR.md](REGIONS-AR.md) e busca alimentar a mesma discussão de desenho (issues
#23, #25, #31 e #54). A versão legível por máquina é [regions-br-proposed.json](regions-br-proposed.json), e a versão
em inglês, que é a referência, é [REGIONS-BR.md](REGIONS-BR.md).

Nada aqui muda o aplicativo, o motor ou uma compilação. Nenhum código lê o JSON, e nada disto é empacotado: as
compilações só empacotam `web/` e `content/`.

**Como foi verificado.** A pesquisa foi feita em 20 de novembro de 2026. Cada fonte tem uma de três marcas:

- **aberta**: o conjunto de dados ou a página de licença foi aberta e lida;
- **só busca**: o fato apareceu em um resultado de busca ou trecho de busca, mas a página não foi aberta;
- **não verificada**: a página não pôde ser acessada ou lida, ou não foi examinada nesta proposta; a linha diz o que falta.

**Segunda verificação.** Um segundo colaborador conferiu a proposta de novo entre 18 e 24 de novembro de 2026
(continuação do #346), em parte com agentes de pesquisa de IA lendo páginas, arquivos e APIs dos editores. Os fatos
acrescentados nessa etapa têm a marca **segunda verificação**, com **medido** quando um arquivo foi processado, uma
consulta foi rodada ou uma contagem foi feita. As frases que um fato novo substitui foram reescritas; o resto está como
foi incorporado no #346. O estado de São Paulo foi examinado com mais detalhe, então várias contagens abaixo são só de
São Paulo.

As caixas dos estados foram calculadas a partir dos próprios polígonos estaduais do IBGE. A segunda verificação as
recalculou a partir do arquivo de limites do IBGE em resolução completa, o que corrige oito caixas em até 0,05° (veja
"Caixas"), e leu a licença do IBGE para os limites: **CC BY 4.0** (veja "Notas sobre licença"; segunda verificação).

## Por que o Brasil é um caso útil

O Brasil tem um esquema nacional próprio de números de emergência (190, 192, 193 e 199, veja "Pontos de ajuda"), e sete
de seus estados usam códigos de duas letras que coincidem com códigos dos EUA neste repositório. Não foi verificada
nesta proposta uma camada aberta de áreas de CEP. Duas coisas são diferentes dos EUA e vale decidi-las uma vez, porque
outros países de língua portuguesa e espanhola vão levantar o mesmo ponto:

- **Códigos de duas letras coincidem com códigos dos EUA.** Sete códigos brasileiros também são códigos de estado dos EUA
  em `STATE_CODES` (`engine/address_search.py`). É o principal motivo dos códigos com hífen abaixo.
- **Sem tabela CEP-estado verificada.** O CEP de oito dígitos é o que a busca de endereços precisa, mas nenhuma tabela
  oficial CEP-estado foi verificada, então os endereços ainda não podem ser separados por estado.

## O que é uma região

O Brasil tem 26 estados e o Distrito Federal (DF). A proposta é uma região por unidade, 27 no total, no mesmo nível de um
estado dos EUA. O DF é uma unidade federativa com governo próprio, então aqui ele é uma região separada; veja a nota
sobre DF e Goiás abaixo.

### Códigos

A ISO 3166-2:BR dá a cada unidade o prefixo `BR-` e duas letras: `BR-SP` São Paulo, `BR-RJ` Rio de Janeiro, `BR-DF`
Distrito Federal, e assim por diante (os 27 códigos foram lidos no artigo da Wikipédia "ISO 3166-2:BR", que lista os
nomes como na ISO 3166-2 pela ISO 3166/MA; o site da ISO em si não foi aberto).

- **Sete códigos de duas letras coincidem com códigos dos EUA.** Os códigos brasileiros `AL` (Alagoas), `MA` (Maranhão),
  `MS` (Mato Grosso do Sul), `MT` (Mato Grosso), `PA` (Pará), `PR` (Paraná) e `SC` (Santa Catarina) também estão em
  `STATE_CODES` (`engine/address_search.py`), para Alabama, Massachusetts, Mississippi, Montana, Pensilvânia, Porto Rico
  e Carolina do Sul. Um `PA` sozinho já significa Pensilvânia na busca de endereços. Um `PA` brasileiro seria lido do
  mesmo jeito, então os códigos brasileiros não podem ser usados sozinhos.
- **O código com hífen também é necessário para o nome do arquivo.** `carry_over()` em `engine/setup/install.py` mantém
  só os índices de endereço com nome `[A-Z]{2}.sqlite` ou `.json` (linha 335). Um índice chamado `BR-SP.sqlite` ficaria
  para trás na biblioteca antiga, sem aviso, como o REGIONS-MX.md também observa para `MX-AGU`. Mudar `carry_over` seria
  uma decisão dos mantenedores.

### Caixas

As caixas foram calculadas a partir dos polígonos estaduais do IBGE (malhas territoriais, camada estadual, "malha
estadual"), lidos pela API pública de malhas do IBGE na qualidade máxima (`qualidade=maxima`) em 20 de novembro de 2026
(aberta). A API devolve uma feição por unidade: 27 feições, com de 1 a 17 polígonos cada (o Pará tem 17, e o Rio de
Janeiro, 15). Cada vértice de cada polígono foi lido; a caixa foi então alargada em 0,15° e arredondada para fora em
0,01°, a mesma margem que `map_sets.state` usa para estados dos EUA.

Como conferência, as bordas externas batem com os extremos conhecidos do Brasil, lembrados de memória (não conferidos
contra uma lista publicada nesta etapa): o extremo norte de Roraima (cerca de 5,27° N), o extremo sul do Rio Grande do
Sul (cerca de 33,75° S), o extremo leste da Paraíba (cerca de 34,79° O) e a borda oeste do Acre (cerca de 73,99° O).
Essas quatro bordas são definidas por esses estados, e a tabela coincide com elas.

**Recalculado a partir do arquivo em resolução completa (segunda verificação, medido).** O contorno `qualidade=maxima`
da API é uma versão simplificada do limite do IBGE: deixa de fora ilhas pequenas e suaviza o litoral. A segunda
verificação calculou de novo cada caixa a partir da camada estadual do IBGE em resolução completa, a **Malha Municipal
Digital 2022** (`BR_UF_2022.zip`, 13.717.460 bytes, SHA-256 `282ec7f0…1c841bcb`, SIRGAS 2000, de
`geoftp.ibge.gov.br/organizacao_do_territorio/malhas_territoriais/malhas_municipais/municipio_2022/Brasil/BR/`,
baixado em 18 e de novo em 24 de novembro de 2026), pela mesma regra. Cada extensão tirada desse arquivo é igual, até a
quarta casa decimal, à `regiao-limitrofe` que a API do IBGE informa para a unidade
(`servicodados.ibge.gov.br/api/v3/malhas/estados/{id}/metadados`, aberta para as 27 em 18 de novembro e para as oito
abaixo de novo em 24 de novembro). A tabela abaixo traz os valores recalculados. A caixa com margem muda para oito
unidades:

| Código | Borda | Incorporado no #346 | Segunda verificação | Borda definida por, no arquivo em resolução completa |
|---|---|---|---|---|
| `BR-MA` | sul | -10,41 | -10,42 | o polígono principal |
| `BR-RN` | norte | -4,68 | -4,66 | um polígono de ilha separado (5 vértices), ausente do contorno da API |
| `BR-PE` | leste, norte | -32,24, -3,68 | -32,22, -3,65 | um polígono separado de Fernando de Noronha (335 vértices) |
| `BR-AL` | sul | -10,65 | -10,66 | o polígono principal |
| `BR-BA` | sul | -18,49 | -18,50 | o polígono principal |
| `BR-SP` | sul | -25,46 | -25,51 | uma ilhota separada (26 vértices) em -48,04, -25,36, perto da divisa com o Paraná; a borda do polígono principal é -25,3123, também ao sul do -25,3089 da API |
| `BR-PR` | oeste | -54,77 | -54,78 | o polígono principal |
| `BR-SC` | leste | -48,20 | -48,17 | um polígono de ilha separado (83 vértices) |

As outras 19 caixas com margem não mudam; as bordas justas delas se movem menos de 0,003°. A mudança de São Paulo é a
maior, cerca de 5 km.

| Código | IBGE | Nome | Caixa (oeste, sul, leste, norte) | Caixa com margem de 0,15° |
|---|---|---|---|---|
| `BR-RO` | 11 | Rondônia | -66,8103, -13,6937, -59,7744, -7,9759 | -66,97, -13,85, -59,62, -7,82 |
| `BR-AC` | 12 | Acre | -73,9904, -11,1456, -66,6236, -7,1118 | -74,15, -11,30, -66,47, -6,96 |
| `BR-AM` | 13 | Amazonas | -73,8016, -9,8180, -56,0976, 2,2466 | -73,96, -9,97, -55,94, 2,40 |
| `BR-RR` | 14 | Roraima | -64,8253, -1,5806, -58,8869, 5,2718 | -64,98, -1,74, -58,73, 5,43 |
| `BR-PA` | 15 | Pará | -58,8983, -9,8412, -46,0614, 2,5910 | -59,05, -10,00, -45,91, 2,75 |
| `BR-AP` | 16 | Amapá | -54,8763, -1,2362, -49,8757, 4,5088 | -55,03, -1,39, -49,72, 4,66 |
| `BR-TO` | 17 | Tocantins | -50,7421, -13,4682, -45,6993, -5,1684 | -50,90, -13,62, -45,54, -5,01 |
| `BR-MA` | 21 | Maranhão | -48,7552, -10,2618, -41,7961, -1,0493 | -48,91, -10,42, -41,64, -0,89 |
| `BR-PI` | 22 | Piauí | -46,0282, -10,9288, -40,3705, -2,7498 | -46,18, -11,08, -40,22, -2,59 |
| `BR-CE` | 23 | Ceará | -41,4235, -7,8582, -37,2527, -2,7843 | -41,58, -8,01, -37,10, -2,63 |
| `BR-RN` | 24 | Rio Grande do Norte | -38,5821, -6,9827, -34,9685, -4,8164 | -38,74, -7,14, -34,81, -4,66 |
| `BR-PB` | 25 | Paraíba | -38,7656, -8,3030, -34,7931, -6,0259 | -38,92, -8,46, -34,64, -5,87 |
| `BR-PE` | 26 | Pernambuco | -41,3583, -9,4829, -32,3778, -3,8046 | -41,51, -9,64, -32,22, -3,65 |
| `BR-AL` | 27 | Alagoas | -38,2376, -10,5004, -35,1519, -8,8131 | -38,39, -10,66, -35,00, -8,66 |
| `BR-SE` | 28 | Sergipe | -38,2450, -11,5686, -36,3959, -9,5150 | -38,40, -11,72, -36,24, -9,36 |
| `BR-BA` | 29 | Bahia | -46,5773, -18,3486, -37,3411, -8,5328 | -46,73, -18,50, -37,19, -8,38 |
| `BR-MG` | 31 | Minas Gerais | -51,0461, -22,9228, -39,8568, -14,2332 | -51,20, -23,08, -39,70, -14,08 |
| `BR-ES` | 32 | Espírito Santo | -41,8798, -21,3018, -39,6660, -17,8919 | -42,03, -21,46, -39,51, -17,74 |
| `BR-RJ` | 33 | Rio de Janeiro | -44,8893, -23,3689, -40,9579, -20,7632 | -45,04, -23,52, -40,80, -20,61 |
| `BR-SP` | 35 | São Paulo | -53,1101, -25,3580, -44,1614, -19,7797 | -53,27, -25,51, -44,01, -19,62 |
| `BR-PR` | 41 | Paraná | -54,6202, -26,7171, -48,0235, -22,5163 | -54,78, -26,87, -47,87, -22,36 |
| `BR-SC` | 42 | Santa Catarina | -53,8371, -29,3551, -48,3279, -25,9558 | -53,99, -29,51, -48,17, -25,80 |
| `BR-RS` | 43 | Rio Grande do Sul | -57,6497, -33,7512, -49,6914, -27,0823 | -57,80, -33,91, -49,54, -26,93 |
| `BR-MS` | 50 | Mato Grosso do Sul | -58,1687, -24,0686, -50,9229, -17,1663 | -58,32, -24,22, -50,77, -17,01 |
| `BR-MT` | 51 | Mato Grosso | -61,6334, -18,0416, -50,2248, -7,3490 | -61,79, -18,20, -50,07, -7,19 |
| `BR-GO` | 52 | Goiás | -53,2486, -19,4984, -45,9072, -12,3950 | -53,40, -19,65, -45,75, -12,24 |
| `BR-DF` | 53 | Distrito Federal | -48,2858, -16,0500, -47,3084, -15,5018 | -48,44, -16,20, -47,15, -15,35 |

Notas:

- **DF dentro de Goiás.** A caixa do DF fica inteiramente dentro da caixa `BR-GO`, o mesmo caso de CABA dentro de Buenos
  Aires em REGIONS-AR.md. A região metropolitana de Brasília cruza a fronteira entre DF e Goiás, então quem mora ali e
  instala só um dos dois mapas perde parte da sua área. Opções: manter os dois mapas separados (simples), ou fazer o mapa
  `BR-GO` incluir `BR-DF` (acompanha como as pessoas se deslocam na região, como o REGIONS-AR.md sugere para CABA). Esta
  proposta não decide isso.
- **Caixas grandes.** Amazonas, Pará e Mato Grosso são as maiores caixas. Os mapas deles serão grandes, e o tamanho do
  download não foi estimado nesta proposta.
- **Ilhas oceânicas.** As malhas do IBGE foram conferidas para todas as unidades: qualquer polígono a mais de 0,5° do
  maior polígono da unidade foi listado. Duas ilhas afastadas estão nas malhas, e duas ilhas oceânicas não estão nelas.
  - **Fernando de Noronha** (`BR-PE`, cerca de 2,4° a leste do continente) é **mantida** na caixa de PE, porque é uma
    ilha de Pernambuco com moradores, e nenhum outro mapa a cobriria. A borda justa dela é -32,38° O, então a caixa de
    PE com margem vai até -32,22° O (segunda verificação, arquivo em resolução completa; o contorno da API dava -32,40 e
    -32,24).
    Sem Noronha a caixa terminaria em -34,81° O; o custo é cerca de 2,4° de oceano. O IBGE lista Fernando de Noronha como
    *Distrito Estadual*, com geocódigo próprio, ao lado dos 5.569 municípios e do Distrito Federal (nota de limites do
    IBGE, aberta; segunda verificação).
  - **Trindade e Martim Vaz** (`BR-ES`, cerca de 10° a leste do continente, perto de 20,5° S) ficam **fora** da caixa do
    ES. Mantê-las esticaria a caixa do ES de -39,67° O até -28,85° O (o arquivo em resolução completa, que também tem
    Martim Vaz; o contorno da API para em -29,30°; segunda verificação), cerca de 13° de largura quase toda de oceano, e a
    caixa deixaria de servir ao continente. Se precisam de um mapa próprio é uma pergunta em aberto. Nenhuma população
    residente foi verificada para elas.
  - **Atol das Rocas** (RN) e **São Pedro e São Paulo** (PE) **não estão nas malhas estaduais do IBGE**, então nenhuma
    caixa as inclui e nada precisa ser cortado. Se alguma deve ter mapa é uma pergunta em aberto.
  - A regra usada aqui: uma ilha entra na caixa do seu estado só se faz parte do polígono do IBGE do estado **e** ou
    está perto do continente ou tem gente morando nela. Só Noronha passa nesse teste. É uma proposta, não uma regra
    fechada.
- **Caixas sobrepostas.** As caixas seguem o contorno de cada estado, então estados vizinhos se sobrepõem ao longo das
  fronteiras. A sobreposição é esperada e é a mesma dos EUA e do México.

## Fontes, camada por camada

| Camada (arquivo) | Fonte dos EUA hoje | Proposta para o Brasil | Publicador | Licença | Verificado |
|---|---|---|---|---|---|
| Relevo (`terrain.sqlite`) | USGS 3DEP | **ANADEM v1.0** (segunda verificação): modelo digital de terreno (solo nu) de 30 m da América do Sul, feito removendo o viés da vegetação do Copernicus GLO-30, sobre o geoide EGM2008 | IPH-UFRGS com a ANA | CC BY 4.0 no registro do OpenTopography (doi:10.5069/G9736P4G); a página da UFRGS não declara licença | aberta (segunda verificação); acurácia vertical não lida |
| Relevo, alternativa | | **TOPODATA** (segunda verificação): 1″ (cerca de 30 m) a partir do SRTM, só Brasil, GeoTIFF otimizado para nuvem. Modelo de superfície, como o Copernicus | INPE | CC BY 4.0 (campo `license` do registro STAC do INPE) | aberta (segunda verificação) |
| Relevo, reserva | | Copernicus DEM GLO-30, como alternativa em REGIONS-AR.md e REGIONS-MX.md | ESA / Airbus | licença Copernicus | Copernicus como em REGIONS-AR.md |
| Água (`water.sqlite`) | NHD | Vias e áreas de água do OSM, como nos EUA. A BHO 6 da ANA não é proposta: a licença é só "acesso livre" (veja Água) | colaboradores do OSM; ANA | ODbL (lida em 20/11/2026) | ODbL aberta; metadados da ANA abertos, sem licença nomeada |
| Barragens | NID | **SNISB** (segunda verificação), o cadastro nacional de segurança de barragens, "Barragens Cadastradas": pontos com altura, capacidade do reservatório, uso, categoria de risco e dano potencial. 28.127 barragens no país, 1.515 em São Paulo, todas com coordenadas. `waterway=dam` do OSM como alternativa | ANA, com dados lançados por cada órgão fiscalizador; colaboradores do OSM | sem licença no item (`licenseInfo` vazio); veja "Água"; ODbL | aberta; contagens lidas do FeatureServer do SNISB em 19/11/2026 (segunda verificação, medido) |
| Culturas (`crops.sqlite`) | USDA Cropland Data Layer | **MapBiomas Brasil Coleção 11.0** (segunda verificação), uso e cobertura da terra anuais de 1985 a 2025, GeoTIFF de 30 m. As classes incluem 46 Café, 47 Citros, 48 Outras lavouras perenes, 35 Dendê, 20 Cana, 39 Soja, 40 Arroz, 41 Outras lavouras temporárias e 9 Silvicultura; não há classe separada para uva ou frutas vermelhas (a uva cai em 48) | MapBiomas | CC BY 4.0 segundo o README do kit de usuário do MapBiomas e a entrada do catálogo do Earth Engine (Coleção 10); um resultado de busca da página de termos dizia CC BY-SA, como o REGIONS-PY.md também encontrou | README e legenda da Coleção 11 abertos (segunda verificação); a página de termos recusou a conexão, só busca |
| Edifícios (`buildings.sqlite`) | Microsoft, contornos dos EUA, alturas do OSM | Google Open Buildings V3 (o Brasil está na lista de países; segunda verificação); Google Open Buildings 2.5D Temporal para presença e **altura** de edifícios, 2016 a 2023 (Brasil listado; segunda verificação); Microsoft Global ML Building Footprints (1.152 blocos do Brasil na lista de links de 24/07/2026; segunda verificação); OSM para preencher lacunas | Google; Microsoft; colaboradores do OSM | CC BY 4.0 ou ODbL 1.0, à escolha do usuário (Google); **CDLA Permissive 2.0** (Microsoft, veja "Notas sobre licença"); ODbL | aberta (segunda verificação); cobertura não medida |
| Lugares (`places.sqlite`) | GNIS, gazetteers do Census, OSM | Malhas do IBGE para estados, municípios e localidades (a camada estadual foi usada para as caixas); **Localidades do Brasil 2022** do IBGE, 96.163 lugares nomeados como pontos com código do município, 6.710 em São Paulo (segunda verificação); lugares nomeados do OSM | IBGE; colaboradores do OSM | Malhas: **CC BY 4.0** (nota de limites do IBGE, veja "Notas sobre licença"; segunda verificação). Localidades: sem arquivo de licença no zip; provavelmente coberta como produto derivado das malhas, não confirmado. ODbL | camada estadual aberta; licença aberta (segunda verificação); Localidades aberta e contada (segunda verificação, medido) |
| Endereços (`addresses/<código>.sqlite`) | endereços Overture | Endereços Overture: 89.887.635 linhas brasileiras na tabela por país do editor. A fonte é o **CNEFE** do IBGE, o cadastro de endereços do Censo 2022, que traz o código do estado em cada registro (segunda verificação, veja "Endereços na Overture") | Overture Maps Foundation; IBGE | página de atribuição da Overture: "IBGE … Available under CC0" (segunda verificação); CEP não aberto | guia Overture aberto em 20/11/2026; página de atribuição aberta (segunda verificação); guia dos Correios aberto (segunda verificação) |
| Pontos de interesse (linhas `poi`) | OSM | Tags do OSM para água potável, hospitais, clínicas, bombeiros e polícia (contagens em "Água" e "Pontos de ajuda e contagens"); CNES como candidato para estabelecimentos de saúde, com coordenadas (segunda verificação) | colaboradores do OSM; Ministério da Saúde (DATASUS) | ODbL (lida); conjunto CNES cc-by (lido) | contado pela Overpass, 20/11/2026; arquivo do CNES processado (segunda verificação, medido) |

## Pontos de ajuda e contagens

- **Estabelecimentos de saúde: CNES (candidato).** A página do conjunto CNES no DATASUS (dadosabertos.saude.gov.br, aberta
  em 20 de novembro de 2026) dá o campo de licença como `cc-by` ("Creative Commons Atribuição"). Isso passa no teste: uso
  comercial e adaptação são permitidos com atribuição. **O arquivo tem coordenadas** (segunda verificação, medido): o
  arquivo completo (`cnes_estabelecimentos_csv.zip`, 57 MB com um CSV de 233 MB, separado por `;`, Latin-1, atualizado
  diariamente; a cópia lida era de 18 de novembro de 2026) tem `NU_LATITUDE` e `NU_LONGITUDE`. Das 643.594 linhas,
  584.475 têm coordenadas; 503.559 estão ativas (sem `CO_MOTIVO_DESAB`, o motivo de desativação). As coordenadas são
  informadas por cada estabelecimento, então algumas estarão erradas. O tipo 22 (*consultório isolado*, cerca de 312 mil
  linhas) deve ficar de fora. Um arquivo separado de UBS escreve a longitude com vírgula decimal e a latitude com ponto.
  As contagens de São Paulo estão em "São Paulo em detalhe".
- **Ressalva sobre o CNES.** O rodapé do mesmo portal diz que o conteúdo do site é CC BY-ND 3.0 (sem adaptação). Isso se
  refere ao texto do próprio site, não ao conjunto de dados. Os mantenedores devem confirmar que a licença do conjunto é a
  que vale para os dados.
- **Postos de bombeiros e polícia.** As listas estaduais não foram verificadas. As contagens do OSM abaixo são os únicos
  números nacionais desta etapa. Para São Paulo, a segunda verificação procurou no portal de dados abertos do estado:
  não foi encontrada lista aberta dos postos do Corpo de Bombeiros da Polícia Militar nem das delegacias; os conjuntos da
  Secretaria da Segurança Pública ali são estatísticas criminais (aberta; segunda verificação).
- **Abrigos.** Nenhuma lista nacional aberta de abrigos foi encontrada; `amenity=shelter` do OSM não foi contado aqui. Em
  São Paulo, `amenity=shelter` marca pequenas coberturas, como o REGIONS-PY.md encontrou para o Paraguai: de 899 contados
  num segundo servidor Overpass com dados de 1º de junho de 2026, 318 são abrigos de piquenique, 176 telheiros, 159 sem
  tipo, 133 pavilhões, 63 gazebos, 41 de transporte público e 9 de outros tipos. `social_facility=shelter` é em sua maioria
  abrigo para pessoas em situação de rua (13 de 29). Nenhum dos dois deve ser desenhado como abrigo de emergência
  (segunda verificação, medido).
- **Documentos de planos de dados do Ministério da Saúde** são descritos nos resultados de busca como CC BY-NC-SA (não
  abertos). Essa licença não é usada em nenhum conjunto aqui.

| Unidade | `amenity=drinking_water` | `man_made=water_tap` | `natural=spring` | `man_made=water_well` | `amenity=hospital` | `amenity=clinic` | `amenity=fire_station` | `amenity=police` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `BR-AC` | 1 | 0 | 19 | 1 | 26 | 21 | 1 | 21 |
| `BR-AL` | 5 | 0 | 6 | 93 | 111 | 154 | 10 | 82 |
| `BR-AP` | 0 | 0 | 2 | 1 | 38 | 89 | 5 | 46 |
| `BR-AM` | 14 | 1 | 19 | 6 | 131 | 147 | 11 | 77 |
| `BR-BA` | 32 | 12 | 103 | 26 | 656 | 1.163 | 25 | 529 |
| `BR-CE` | 60 | 5 | 15 | 168 | 344 | 680 | 19 | 253 |
| `BR-DF` | 34 | 12 | 21 | 2 | 126 | 190 | 42 | 202 |
| `BR-ES` | 41 | 3 | 15 | 3 | 144 | 432 | 20 | 250 |
| `BR-GO` | 29 | 2 | 111 | 14 | 327 | 312 | 34 | 213 |
| `BR-MA` | 5 | 1 | 4 | 23 | 228 | 178 | 16 | 118 |
| `BR-MT` | 4 | 7 | não contado | 3 | 181 | 270 | 25 | 172 |
| `BR-MS` | 9 | 0 | 174 | 6 | 115 | 87 | 19 | 121 |
| `BR-MG` | 142 | 15 | 1.697 | 54 | 860 | 1.234 | 63 | 656 |
| `BR-PA` | 42 | 0 | 23 | 16 | 270 | 229 | 16 | 141 |
| `BR-PB` | 34 | 14 | 15 | 83 | 213 | 271 | 18 | 107 |
| `BR-PR` | 101 | 37 | 228 | 33 | 510 | 930 | 92 | 454 |
| `BR-PE` | 18 | 6 | 245 | 40 | 431 | 529 | 30 | 209 |
| `BR-PI` | 9 | 0 | 9 | 29 | 228 | 478 | 3 | 106 |
| `BR-RJ` | 71 | 22 | 727 | 54 | 603 | 797 | 118 | 541 |
| `BR-RN` | 33 | 2 | 5 | 55 | 191 | 439 | 8 | 180 |
| `BR-RS` | 88 | 30 | 84 | 38 | 560 | 1.056 | 132 | 583 |
| `BR-RO` | 3 | 0 | 3 | 0 | 52 | 41 | 6 | 71 |
| `BR-RR` | 12 | 0 | 4 | 2 | 23 | 65 | 6 | 55 |
| `BR-SC` | 34 | 3 | 484 | 20 | 252 | 1.240 | 193 | 459 |
| `BR-SP` | 470 | 92 | 2.411 | 136 | 1.370 | 2.663 | 234 | 2.195 |
| `BR-SE` | 7 | 1 | 7 | 4 | 72 | 274 | 10 | 146 |
| `BR-TO` | 7 | 0 | 11 | 0 | 52 | 75 | 2 | 28 |
| **Total (soma das 27 unidades)** | **1.305** | **265** | **não contado** | **910** | **8.114** | **14.044** | **1.158** | **8.015** |

As contagens são objetos do OSM como encontrados pela Overpass em 20 de novembro de 2026, por unidade (área ISO 3166-2);
a última linha é a soma das 27 unidades. Uma consulta nacional única deu timeout no servidor da Overpass, então o total
do país não foi contado separadamente. Duplicatas e feições fechadas não foram removidas, então são limites superiores,
não totais verificados.

A contagem de `natural=spring` em Mato Grosso está **não contada**. A Overpass dá 53.580 objetos. Para ver de onde eles
vêm, a caixa justa do IBGE para BR-MT (O -61,6334, S -18,0416, L -50,2248, N -7,3490) foi cortada ao meio nos pontos
médios, latitude -12,6953 e longitude -55,9291, e cada quarto foi cruzado com a área BR-MT do OSM. Os quartos têm 31.074
(sudoeste), 19.825 (sudeste), 40 (noroeste) e 2.641 (nordeste), que somam 53.580; uma consulta do estado inteiro em 21
de novembro de 2026 deu o mesmo total. Pelos metadados dos objetos dos dois quartos do sul, 50.807 nascentes (31.006 no
sudoeste e 19.801 no sudeste) estão em oito changesets feitos por um único usuário do OSM (`danctc`) em 6 de novembro de
2025 (174297625, 174297760, 174297826, 174297902, 174298479, 174298489, 174298500 e 174298643). Os oito têm
`source=SEMA-MT` (a secretaria de meio ambiente de Mato Grosso) e nenhum comentário de discussão. Não foi encontrada
permissão para dados da SEMA-MT: a página Contributors da wiki do OSM lista a secretaria de meio ambiente de Minas
Gerais, mas não a SEMA-MT; o Import/Catalogue não tem entrada para ela; e o rodapé do site da SEMA-MT diz "Todos os
Direitos reservados". Os pontos podem ser nascentes reais, mas sem licença documentada não devem ser contados nem
distribuídos, então não há número nessa coluna, e o total dela também não é contado.

### São Paulo em detalhe (segunda verificação)

São Paulo foi examinado mais a fundo, como exemplo do que um mapa estadual teria. As contagens do OSM são da API
Overpass dentro da mesma área `BR-SP` (nós, vias e relações; dados até 18 de novembro de 2026, 21:29 UTC; medido), então
podem diferir em poucas unidades da tabela acima. As contagens oficiais são de estabelecimentos ativos em São Paulo.

| Tipo | Tag do OSM | OSM, SP | Fonte oficial | Oficial, SP |
|---|---|---:|---|---:|
| Hospitais gerais e especializados | `amenity=hospital` | 1.370 | CNES tipos 5 e 7 | 785 e 194 |
| Atendimento de urgência | `emergency=ambulance_station` | 136 | CNES tipos 73 (*pronto atendimento*, incluindo UPAs), 20 (*pronto socorro*) e 42 (unidades móveis de urgência, em sua maioria SAMU) | 458, 85 e 1.086 |
| Atenção básica | `amenity=clinic`, `amenity=doctors` | 2.660 e 541 | CNES tipos 2 (*centro de saúde / UBS*) e 1 (*posto*) | 5.340 e 267 |
| Farmácias | `amenity=pharmacy` | 3.403 | CNES tipo 43 | 4.932 |
| Combustível | `amenity=fuel` | 6.465 | cadastro de revendedores da ANP: endereço e CEP, **sem coordenadas** | 8.389 |
| Escolas | `amenity=school` | 9.046 | rede estadual de São Paulo (Secretaria da Educação, `ENDERECO_ESCOLAS`), com coordenadas, CC BY 4.0 | 5.582 |
| Barragens | `waterway=dam` | 305 | SNISB | 1.515 |
| Caixas-d'água, reservatórios | `man_made=water_tower`, `water=reservoir` | 3.319 e 5.465 | | |
| Supermercados | `shop=supermarket` | 4.229 | | |
| Centros comunitários, prefeituras | `amenity=community_centre`, `amenity=townhall` | 689 e 603 | | |
| Pontos de encontro | `emergency=assembly_point` | 10 | | |

Todas as 116.899 linhas ativas do CNES em São Paulo têm coordenadas, e todas menos uma caem dentro da caixa de São Paulo
(medido). As barragens de São Paulo no SNISB são cadastradas pela SP Águas, a agência estadual de águas que sucedeu o
DAEE (1.256), pela ANEEL (169), pela ANM (58), pela ANA (30) e pela CETESB (2) (medido). O cadastro de combustível da ANP
poderia ser posto no mapa cruzando os endereços com o índice de endereços; os 6.465 do OSM também podem ser usados como
estão.

O geoportal da cidade de São Paulo, o **GeoSampa**, tem camadas de pontos de bombeiros (40), Polícia Civil (93), Polícia
Militar (159), Guarda Civil Metropolitana (48) e Defesa Civil (34), e polígonos de risco geológico (1.404) e hidrológico
(793), com manchas de inundação para 5, 25 e 100 anos (aberto). Estão sob CC BY-SA 4.0 (veja "Notas sobre licença"). O
geoportal ambiental do estado, o **DataGeo**, tem o mapeamento de risco de escorregamento e inundação do Instituto
Geológico de 2014 para 41 municípios e as 19 regionais da Defesa Civil (polígonos), sem licença declarada (aberto). Áreas
de risco são um tipo novo de camada para o Lastbook, não substituem uma dos EUA; se devem aparecer é decisão dos
mantenedores. Não foi encontrada lista aberta de pontos públicos de água potável do estado, da cidade nem da Sabesp.

## Notas sobre licença e atribuição

- **Conteúdo do gov.br.** O rodapé das páginas do gov.br diz que todo o conteúdo é publicado sob a *Creative Commons
  Atribuição-SemDerivações 3.0 Não Adaptada* (CC BY-ND 3.0 Brasil) (aberta; lida em 20 de novembro de 2026 na página
  "Sobre o portal" do gov.br e na página federal do SAMU). A parte "sem derivações" significa que uma página não pode ser
  adaptada para um guia da biblioteca, então as páginas do gov.br não são propostas como fonte de cópia. Citar um número
  único com a fonte é uma questão para os mantenedores, não uma decisão tomada aqui.
- **Malhas do IBGE: CC BY 4.0** (segunda verificação, aberta). A nota técnica "Malha Municipal Digital e Áreas
  Territoriais – Informações Técnicas e Legais" (Notas metodológicas 01/2025, `biblioteca.ibge.gov.br`, liv102169) diz:
  "O IBGE disponibiliza a MMD e todos produtos e informações dela derivados sob licença Creative Commons BY 4.0", e que
  usá-las implica aceitar suas condições e eximir o IBGE de responsabilidade. A nota lida é a da edição 2024; o LEIA-ME do
  zip de 2025 remete à nota. A camada estadual usada para as caixas faz parte do mesmo produto. Isso resolve a licença que
  o texto incorporado deixava em aberto, então as malhas do IBGE podem ser **propostas para uma compilação**, com crédito
  ao IBGE.
- **BC250 do IBGE** (segunda verificação, aberta). O *Termo de Compromisso de Uso* de 2019 da base cartográfica
  1:250.000 diz que é "vedada a locação ou comercialização" sem autorização escrita do IBGE e limita o uso ao "apoio a
  projetos de trabalho". A pasta de 2025 não tem arquivo de licença. Não proposta: Localidades 2022 e as malhas cobrem a
  mesma necessidade.
- **CNEFE do IBGE** (segunda verificação). Não foi encontrada declaração de licença do IBGE nos arquivos do CNEFE. A
  página de atribuição da Overture diz "IBGE (Instituto Brasileiro de Geografia e Estatística). Available under CC0.
  Distributed by AddressForAll. Accessed: 2024-10-13" (aberta). O OpenAddresses marca o mesmo arquivo como exigindo
  atribuição ao IBGE (aberta). A wiki do OSM diz que o IBGE não deu declaração clara de licença (aberta). O IBGE é um
  órgão público federal, e seus dados publicados se enquadram na política federal de dados abertos abaixo. A proposta é
  usar o CNEFE, pela Overture ou diretamente, com crédito ao IBGE, o que atende tanto à CC0 quanto a uma licença de
  atribuição.
- **Política federal de dados abertos** (segunda verificação, aberta). O Decreto 8.777/2016, art. 4º com a redação do
  Decreto 9.903/2019, diz que os dados abertos do Poder Executivo federal são "de livre utilização pelos Poderes Públicos
  e pela sociedade"; a definição de dados abertos no art. 2º só pede que se credite a autoria ou a fonte. Os termos do
  `dados.gov.br` (Resolução CGINDA nº 2/2017) permitem o uso "para qualquer finalidade", inclusive com fins lucrativos,
  reprodução e distribuição, "desde que citada a devida fonte", salvo quando o conjunto tem licença própria, e listam CC0,
  PDDL, CC BY 4.0 e ODbL como as licenças que os órgãos devem escolher. O texto incorporado viu essa resolução só em busca;
  ela foi aberta na segunda verificação. Se o alcance do decreto cobre cada editor (fundações e agências federais como o
  IBGE e a ANA) não foi relido no art. 1º do decreto.
- **Microsoft Global ML Building Footprints: CDLA Permissive 2.0** desde 11 de março de 2026 (commit `ef94ee3d` em
  `microsoft/GlobalMLBuildingFootprints`; antes era ODbL; aberto, segunda verificação). A página de atribuição da Overture
  ainda a lista como ODbL.
- **MapBiomas.** CC BY 4.0 segundo o README do kit de usuário e o catálogo do Earth Engine, com o crédito "MapBiomas
  Project – Collection [version] of the Annual Series of Land Use and Land Cover Maps of Brazil, accessed on [date]
  through the link: [link]" (aberto, segunda verificação). Um resultado de busca da página de termos dizia CC BY-SA, e a
  página recusou a conexão (só busca). A confirmar com o MapBiomas antes de uma compilação.
- **ANADEM e TOPODATA: CC BY 4.0** (segunda verificação, aberta). O crédito do ANADEM é "Distributed by OpenTopography.
  https://doi.org/10.5069/G9736P4G", com ANA (2025) e Laipelt et al. 2024, *Remote Sensing* 16, 2321.
- **Estado e cidade de São Paulo** (segunda verificação, aberta). O portal de dados abertos do estado
  (`dadosabertos.sp.gov.br`) tem 456 conjuntos, 338 deles em CC BY 4.0 e o resto sem licença; o arquivo das escolas
  estaduais é CC BY 4.0. O GeoSampa (cidade de São Paulo) é **CC BY-SA 4.0** pela "Licença para uso de dados do GeoSampa"
  da prefeitura (processo SEI 6066.2020/0003044-4): o compartilhamento pela mesma licença amarraria um pacote que o
  contivesse, e a CC BY-SA 4.0 não é a ODbL, então misturá-lo numa base feita do OSM exige decisão. O DataGeo (meio
  ambiente do estado) não declara licença nas páginas Sobre e FAQ nem num registro de amostra. O Instituto Geográfico e
  Cartográfico (IGC) vende seus mapas e diz "Todos os direitos reservados". Nada nesta proposta depende do GeoSampa, do
  DataGeo ou do IGC.

## Água: potável e limpa

Esta é a prioridade do Brasil, então está descrita por inteiro. Para cada fonte, a pergunta é a mesma do resto do mapa:
a biblioteca pode copiar, e dá para usar offline?

**Proposto**

- **Camada de água: OpenStreetMap, sob a ODbL.** Vias e áreas de água, como na compilação dos EUA. O texto da ODbL 1.0 foi
  lido na página de licença em 20 de novembro de 2026 (aberta): uso comercial permitido, uma base de dados feita a partir
  de dados do OSM é compartilhada sob a mesma licença, e a atribuição é "© OpenStreetMap contributors".
- **Pontos de água potável: tags do OSM.** `amenity=drinking_water` (torneira ou bebedouro público), `man_made=water_tap`,
  `natural=spring` e `man_made=water_well`. Uma tag não diz que a água é potável; por isso nascentes e poços recebem o
  rótulo simples "não verificada para beber", como o REGIONS-ES.md propõe para a Espanha.
- **Contagens por unidade** estão em "Pontos de ajuda e contagens", abaixo (API Overpass, 20 de novembro de 2026).

**Não proposto (falha no teste de licença)**

- **ANA Base Hidrográfica Ottocodificada (BHO 6).** O registro de metadados (metadados.snirh.gov.br, aberto em 20 de
  novembro de 2026) dá a licença como "O acesso ao dado é livre." Isso não nomeia licença, e nada diz que o dado pode ser
  adaptado ou usado comercialmente. Não proposto até a ANA nomear uma. Próximo passo: perguntar à ANA e conferir a página
  do conjunto em dadosabertos.ana.gov.br.
  A página de dados abertos da própria ANA (`gov.br/ana/pt-br/acesso-a-informacao/dados-abertos/dados-abertos/`) diz que
  seus dados são "disponibilizados livremente … sem restrição de licenças, patentes ou mecanismos de controle" (aberta,
  segunda verificação). Com a política federal de dados abertos em "Notas sobre licença", isso pode bastar para os
  mantenedores aceitarem a BHO 6 com crédito à ANA; a decisão é deles. A BHO 6 é a v6.2.4 de 20 de outubro de 2022, em
  GeoPackage; o arquivo de trechos de drenagem tem 4,06 GB e o de áreas de contribuição 20,1 GB, então uma compilação a
  recortaria por estado. A BHAE v1.0 (28 de março de 2023) é uma versão mais leve, com rios de área de drenagem de 10 km²
  ou mais (aberta, segunda verificação).
- **CPRM SIAGAS (poços de água subterrânea).** O portal web do SIAGAS (siagasweb.sgb.gov.br, aberto em 20 de novembro de
  2026) não tem texto de licença nem de termos. Os acordos e relatórios encontrados descrevem licenças de software, não de
  dados, e um documento de 2008 diz que os dados completos exigem pedido por escrito. Não proposto; poços do OSM ocupam
  o lugar. Próximo passo: pedir à CPRM a licença dos dados.
- **Barragens.** A etapa incorporada não encontrou lista nacional aberta. A segunda verificação encontrou o **SNISB**, o
  cadastro nacional de segurança de barragens da ANA (item de dados abertos
  `dadosabertos.ana.gov.br/datasets/24d0145e38c545889fd5dd8d7aeaef32_0`, FeatureServer
  `snirh.gov.br/arcgis/rest/services/IG/SNISB/FeatureServer/0`; CSV, Shapefile, GeoJSON, KML), com coordenadas para
  cada barragem: 28.127 no país e 1.515 em São Paulo em 19 de novembro de 2026 (medido). O campo de licença do item está
  vazio, então ele fica onde a BHO 6 fica: a declaração de dados abertos da ANA acima é a base, e a decisão é dos
  mantenedores.

## Pontos de ajuda

Os números de emergência são a parte de que as pessoas mais precisam, e são os mesmos no país inteiro. Os números
principais têm como fonte o Ministério das Comunicações. 112 e 911 não são números de emergência próprios: são
redirecionamentos condicionais (veja a nota abaixo da tabela).

| Serviço | Número | Fonte do número | Dados de localização |
|---|---|---|---|
| Ambulância (SAMU) | 192 | Ministério das Comunicações, "Emergência: você sabe para quem ligar quando precisa de ajuda?", publicado em 11/09/2026, atualizado em 27/10/2026 (aberto em 21/11/2026), [link](https://www.gov.br/mcom/pt-br/noticias/2026/setembro/emergencia-voce-sabe-para-quem-ligar-quando-precisa-de-ajuda/) | não verificados |
| Incêndio (Corpo de Bombeiros) | 193 | Ministério das Comunicações, "Emergência: você sabe para quem ligar quando precisa de ajuda?", publicado em 11/09/2026, atualizado em 27/10/2026 (aberto em 21/11/2026), [link](https://www.gov.br/mcom/pt-br/noticias/2026/setembro/emergencia-voce-sabe-para-quem-ligar-quando-precisa-de-ajuda/) | serviços estaduais de bombeiros: não verificados |
| Polícia (Polícia Militar) | 190 | Ministério das Comunicações, "Emergência: você sabe para quem ligar quando precisa de ajuda?", publicado em 11/09/2026, atualizado em 27/10/2026 (aberto em 21/11/2026), [link](https://www.gov.br/mcom/pt-br/noticias/2026/setembro/emergencia-voce-sabe-para-quem-ligar-quando-precisa-de-ajuda/) | polícia estadual: não verificada |
| Redirecionamento condicional ao serviço de emergência brasileiro (celular) | 112 e 911 | [Resolução Anatel 777, art. 127](https://informacoes.anatel.gov.br/legislacao/resolucoes/2025/2022-resolucao-777) (aberta em 21/11/2026): redirecionados só "se houver viabilidade técnica"; a página de códigos da Anatel os lista como só celular | polícia estadual: não verificada |
| Defesa civil (Defesa Civil) | 199 | Ministério das Comunicações, "Emergência: você sabe para quem ligar quando precisa de ajuda?", publicado em 11/09/2026, atualizado em 27/10/2026 (aberto em 21/11/2026), [link](https://www.gov.br/mcom/pt-br/noticias/2026/setembro/emergencia-voce-sabe-para-quem-ligar-quando-precisa-de-ajuda/) | não verificados |

Notas:

- 112 e 911 são redirecionamentos condicionais. O art. 127 da Resolução Anatel 777 diz que, "se houver viabilidade
  técnica", a chamada para 112 ou 911 é redirecionada ao respectivo serviço público de emergência brasileiro. Quem ler
  deve ligar primeiro para 190, 192, 193 ou 199; 112 e 911 podem não completar.
- As listas oficiais não foram verificadas: o cadastro nacional de saúde (CNES) e as listas estaduais de postos de
  bombeiros e polícia. As contagens do OSM de hospitais, clínicas, bombeiros e polícia estão em "Pontos de ajuda e
  contagens". A segunda verificação processou depois o CNES e procurou as listas estaduais de São Paulo; veja "Pontos de
  ajuda e contagens".
- A tabela de números em si pertence à [issue #261](https://github.com/Immortal-Protocols/lastbook/issues/261), não a esta
  proposta de mapa. Ela aparece aqui para que o mapa e a tabela de números coincidam.

## Como conferir uma mudança de mapa

- Uma mudança em uma camada de `web/map.js` é uma mudança visível: inclua capturas de tela no modo claro e escuro.
- Uma mudança em uma ferramenta de pacote ou de mapa: `packaging/test_pack_tools.py` e `packaging/scan_pack.py` conferem o
  que um conjunto de mapas pode ter, e `scan_pack.py` lista os arquivos permitidos em `derived/geo/` (`GEO_FILES`).
- Nada que um colaborador adicione pode fazer o aplicativo abrir uma conexão. Dados novos entram por uma ferramenta de
  compilação e chegam como arquivo.

Licenças lidas para esta proposta (20 de novembro de 2026):

- **ODbL 1.0** (água e pontos do OSM): uso comercial permitido; base derivada compartilhada sob a ODbL; atribuição
  "© OpenStreetMap contributors". Lida na página de licença do opendatacommons.org.
- **CC BY 4.0** (Google Open Buildings; campo `cc-by` do conjunto CNES): adaptar, inclusive comercialmente, com atribuição.
  Lida no deed do creativecommons.org.
- **Conjunto CNES** (`cc-by`, do campo de licença do conjunto): veja a ressalva em "Pontos de ajuda e contagens".
- **Sem licença, não proposto:** ANA BHO 6 ("acesso livre" apenas); CPRM SIAGAS (sem texto de licença); conteúdo do gov.br
  (CC BY-ND 3.0, sem adaptação).

## Endereços na Overture, segundo o guia do editor

- **Brasil: 89.887.635 endereços**, na tabela por país do guia de endereços da Overture
  (docs.overturemaps.org/guides/addresses/, aberto em 20 de novembro de 2026). É a contagem do editor, não uma contagem
  feita para esta proposta. A mesma tabela traz EUA e México (México 30.726.687, como o REGIONS-MX.md lê).
- Contagens por estado não foram calculadas. O primeiro dígito do CEP não é código de estado (veja abaixo), então dividir
  por ele colocaria endereços no estado errado.
- **Fonte: o CNEFE do IBGE** (segunda verificação, aberta). A página de atribuição da Overture dá o IBGE, distribuído pela
  AddressForAll, como fonte das linhas brasileiras (veja "Notas sobre licença"). O CNEFE (*Cadastro Nacional de Endereços
  para Fins Estatísticos*) é o cadastro de endereços que o IBGE montou para o Censo 2022. O IBGE o publica abertamente, um
  arquivo por estado (`ftp.ibge.gov.br/Cadastro_Nacional_de_Enderecos_para_Fins_Estatisticos/Censo_Demografico_2022/`; o
  CSV de São Paulo tem 1,0 GB, de 20 de maio de 2024, e há versão GeoJSON), com tipo, título e nome do logradouro,
  número, CEP, localidade, setor censitário, nome do estabelecimento, latitude e longitude. O arquivo do Acre tem 410.524
  linhas (medido). Um arquivo só de coordenadas para São Paulo tem **22.953.725 linhas** (medido). O IBGE informou 106,8
  milhões de endereços no país, 22,8% sem número (só busca); por que a Overture tem menos não foi verificado.
- **Dá para separar por estado sem tabela de CEP** (segunda verificação). Cada registro do CNEFE traz o código IBGE do
  estado (`COD_UF`) e o código do município, então uma compilação que lê o CNEFE diretamente pode cortar por estado com
  exatidão. Uma compilação que lê a Overture pode usar os polígonos estaduais, que agora são CC BY 4.0 (veja "Notas sobre
  licença").
- **Qualidade da coordenada** (segunda verificação, medido). Cada registro do CNEFE tem um nível, `NV_GEO_COORD`: 1 é o
  ponto original do censo, 2 um ponto deslocado para apartamentos que dividem um número, 3 uma estimativa, e 4 a 6 só o
  situam na face de quadra, na localidade ou no setor censitário. No arquivo do Acre, 95% são de nível 1. Um índice
  poderia manter os níveis 1 a 3 e descartar o resto.
- O guia da Overture diz que os IDs de endereço não são estáveis o bastante para entrar no registro GERS, então podem
  mudar entre versões. Uma compilação precisaria de uma versão fixa.

## Como os endereços são escritos

Lido do *Guia Técnico de Endereçamento de Correspondências* dos Correios (versão 1.4, 2021) e da página do guia de
endereçamento dos Correios: **só trechos de busca**; o PDF não foi aberto. A segunda verificação abriu o guia (versão
1.4, de 3 de maio de 2021), a página do guia de endereçamento e a página "Tudo sobre CEP" dos Correios; os fatos tirados
deles estão marcados abaixo.

- **CEP.** Oito dígitos, escritos `00000-000` com hífen depois do quinto dígito, por exemplo `01311-000` (o exemplo dos
  Correios). A API dos Correios aceita oito dígitos sem hífen. Guardar como texto, porque ocorrem zeros à esquerda.
- **Ordem.** Tipo de logradouro, nome da rua e número, depois complemento e bairro, depois cidade e UF, com o CEP por
  último. O guia dos Correios coloca o CEP sozinho na última linha de um endereço escrito à mão. O exemplo do próprio guia
  é "Avenida Paulista 123, Loja B / Paraíso / 01311-000 São Paulo/SP", com cidade e UF separadas por "/" (aberta, segunda
  verificação).
- **Tipos de logradouro** (segunda verificação). Os Correios listam 41 tipos, entre eles *rua*, *avenida*, *alameda*,
  *travessa*, *praça*, *estrada*, *rodovia*, *largo*, *viela*, *ladeira* e *vila* (aberta), e não publicam tabela de
  abreviações. O arquivo do CNES para São Paulo mostra como são escritos na prática: `RUA` (57.882), `AVENIDA` (15.325),
  `AV` (9.578), `R` (5.986), e `PRACA`, `ALAMEDA`, `AL`, `AVN`, `ROD`, `ESTRADA` e `TRAVESSA` (medido). Endereços de
  beira de estrada muitas vezes trazem o quilômetro dentro do campo do logradouro, como "ROD WASHINGTON LUIZ KM 234"
  (medido).
- **Sem número.** Os Correios escrevem `SN` (*sem número*). O complemento do CEP fica então `00000` (só trecho de busca).
  O próprio guia recomenda a sigla `s/n` ("Para os logradouros sem numeração recomenda-se a utilização da sigla s/n";
  aberta, segunda verificação); os dados têm `S/N` e `SN`.
- **Estrutura do CEP** (segunda verificação, aberta, "Tudo sobre CEP" dos Correios). O primeiro dígito é uma de dez
  regiões postais, numeradas no sentido anti-horário a partir do estado de São Paulo; os quatro seguintes indicam
  sub-região, setor, subsetor e divisor de subsetor. O sufixo de três dígitos separa logradouros (000 a 899) de códigos
  especiais (900 a 959), códigos promocionais (960 a 969) e unidades dos Correios (970 a 989 e 999), com 990 a 998 para
  caixas postais comunitárias. O banco de CEP dos Correios (DNE) é um produto licenciado vendido por tabela de preços
  ("Produto licenciado, com restrições de uso e proteção por direitos autorais"; aberta), então não é aberto. O CNEFE traz
  o CEP nos registros, então não é preciso outra fonte de CEP.
- **O CEP não é código de estado.** O primeiro dígito é uma região ampla, não um estado, e nenhuma tabela CEP-estado foi
  verificada. Os índices de endereço não podem ser divididos por estado até achar uma tabela ou usar um polígono estadual.
  A segunda verificação encontrou que o código de estado do CNEFE resolve isso (veja "Endereços na Overture").
- **O que o código faz hoje** (lido neste repositório, 20 de novembro de 2026):
  - `tools/build_addresses.py` mantém só `country = 'US'`; as linhas brasileiras precisariam mudar o país.
  - `normalize()` em `engine/address_search.py` troca cada caractere fora de `a-z` e `0-9` por um espaço, então acentos
    do português separam palavras: "Ação" vira "a o". Seria preciso tirar acentos, como o REGIONS-MX.md observa para o
    espanhol.
  - `is_address_query()` exige um número primeiro, então "Rua do Lago 50, 01311" hoje não é tratado como endereço.
  - Testado em 18 de novembro de 2026 (segunda verificação, medido): "Av. Paulista, 1578, Bela Vista, São Paulo - SP,
    01310-200" e "Rua Conceição, 233, Campinas, SP" não são tratados como endereço; só a ordem dos EUA, "1578 Avenida
    Paulista", é.
  - Quem digita sem acento, como muita gente faz no celular, obtém `rua conceicao`, enquanto o índice guarda
    `rua concei o`, então os dois não coincidem (segunda verificação, medido).
  - As palavras de logradouro em `normalize()` são em inglês: `av` vira `ave`, mas `avenida` continua `avenida`, então
    "Av Paulista" e "Avenida Paulista" não coincidem entre si. Os tipos de logradouro em português precisariam de tabela
    própria (segunda verificação, medido).
  - O CEP não é lido como código postal: o analisador procura cinco dígitos no fim, e "01310-200" vira `01310 200`. O
    `build_addresses.py` mantém `left(postcode, 5)`, que para um CEP guarda da região ao subsetor (`01310`), uma chave
    útil se o analisador ler os mesmos cinco dígitos. Como a Overture escreve os CEPs brasileiros não foi verificado
    (segunda verificação).
  - O buscador de lugares já funciona: o índice FTS5 usa o tokenizador `unicode61`, que tira acentos. Testado em 18 de
    novembro de 2026: `sao paulo`, `ribeirao`, `sao jose campos`, `guaruja`, `conceicao`, `barbara oeste` e `embu guacu`
    encontraram "São Paulo", "Ribeirão Preto", "São José dos Campos", "Guarujá", "Conceição de Macabu", "Santa Bárbara
    d'Oeste" e "Embu-Guaçu" (segunda verificação, medido).

## Ainda por decidir

Cada item precisa de decisão dos mantenedores antes de qualquer mudança de código.

1. **Códigos no setup.** Se `BR-AC` e os outros servem como `id` no manifesto, e a regra de `carry_over()` em
   `engine/setup/install.py` (linha 335), que mantém só nomes `[A-Z]{2}`.
2. **DF e Goiás.** Mapas separados, ou o mapa de Goiás inclui o DF (sobreposição de caixas, como CABA no REGIONS-AR.md).
3. **Trindade e Martim Vaz.** Um mapa pequeno próprio, ou nenhum mapa. Nenhuma população residente foi verificada.
4. **Atol das Rocas e São Pedro e São Paulo.** Não estão nas malhas do IBGE; se alguma deve ter mapa.
5. **Licença do IBGE.** As malhas são CC BY 4.0 (segunda verificação). Falta decidir: se Localidades 2022 conta como
   produto derivado pela mesma nota, e como o mapa dá crédito ao IBGE pelo CNEFE (a linha CC0 da Overture, uma linha de
   atribuição, ou as duas).
6. **CEP.** Não foi encontrada fonte aberta de áreas de CEP, e o DNE dos Correios é vendido. A separação por estado não
   depende mais disso: o CNEFE traz o código do estado (segunda verificação). A busca de endereços ainda precisa ler um
   CEP de oito dígitos, o número depois do logradouro, as palavras de logradouro em português e tirar acentos.
7. **Classes de cultura.** As classes do MapBiomas agora são conhecidas (segunda verificação: café, citros, outras
   lavouras perenes e outras), e a licença é CC BY 4.0 segundo o kit de usuário, com uma leitura CC BY-SA a descartar.
   Quais classes correspondem aos tipos pomar, vinhedo e frutas vermelhas em `tools/build_crops.py` ainda está por
   decidir.
8. **Caixas sobrepostas.** As caixas seguem o contorno de cada estado, então vizinhos se sobrepõem nas fronteiras. Se
   isso é aceitável é a mesma pergunta do REGIONS-MX.md.
9. **Fontes de água.** A licença da BHO 6 pela ANA e a licença dos dados do SIAGAS pela CPRM não foram respondidas. As duas
   falham no teste até que uma seja nomeada. A segunda verificação acrescenta a declaração de dados abertos da ANA ("sem
   restrição de licenças"), que vale tanto para a BHO 6 quanto para o cadastro de barragens SNISB; se essa declaração
   basta é decisão dos mantenedores.
10. **CNES.** Confirmar que a licença do conjunto (`cc-by`) vale para os dados do CNES, e não o rodapé do portal
    (CC BY-ND). O arquivo tem coordenadas (segunda verificação).

## O que foi verificado e o que não foi

- **Aberto em 20 de novembro de 2026:** a API de malhas do IBGE, polígonos estaduais em qualidade máxima, para as 27
  unidades; a página "Sobre o portal" do gov.br e o artigo federal do SAMU 192 (licença no rodapé: CC BY-ND 3.0 Brasil);
  a página da Anatel de serviços de utilidade pública e emergência (190, 192, 193, 199, e 112/911 listados como só
  celular); em 21 de novembro de 2026, a notícia do Ministério das Comunicações sobre números de emergência e o art. 127
  da Resolução Anatel 777 (112/911 redirecionados só se houver viabilidade técnica); o guia de endereços da Overture
  (Brasil 89.887.635); o artigo da Wikipédia "ISO 3166-2:BR" (27 códigos, nomes da ISO 3166/MA).
- **Calculado em 20 de novembro de 2026:** as 27 caixas justas e as margens de 0,15° (para baixo em oeste e sul, para
  cima em leste e norte, até 0,01°); a conferência de ilhas destacadas nas 27 unidades; a caixa do ES sem Trindade e
  Martim Vaz.
- **Visto só em resultados de busca:** a nota técnica e legal do IBGE e os termos da BC250 (uso restrito); o guia de
  endereçamento dos Correios; uma resolução federal de 2017 sobre dados abertos que lista CC0, PDDL, CC BY 4.0 e ODbL
  como aceitáveis.
- **Aberto em 20 de novembro de 2026 (água e pontos de ajuda):** a API Overpass (contagens do OSM, oito tags: as 27
  consultas por unidade completaram; a consulta nacional deu timeout); os textos das licenças ODbL 1.0 e CC BY 4.0; o
  registro de metadados da BHO 6 da ANA; o portal web do SIAGAS (sem texto de licença); a página do conjunto CNES (campo
  de licença `cc-by`); o rodapé do portal do CNES (CC BY-ND 3.0 para o site).
- **Verificado em 21 de novembro de 2026 (nascentes de Mato Grosso):** a contagem da Overpass em quatro quartos descrita
  em "Pontos de ajuda e contagens" (31.074 + 19.825 + 40 + 2.641 = 53.580) e uma contagem do estado inteiro (53.580); os
  metadados dos objetos dos quartos sudoeste e sudeste; os oito changesets na API do OSM (usuário, data, número criado,
  `source=SEMA-MT`, sem comentários); a página Contributors e o Import/Catalogue da wiki do OSM (sem entrada da
  SEMA-MT); o rodapé da página inicial da SEMA-MT e o catálogo de dados abertos de Mato Grosso (sem licença para dados
  de nascentes). O portal GeoDados MT não carregou sem navegador, então não foi lido.
- **Visto só em resultados de busca:** os planos de dados abertos do Ministério da Saúde (CC BY-NC-SA); os acordos da CPRM
  sobre o SIAGAS; o texto da política de dados abertos da ANA.
- **Não verificado:** o Online Browsing Platform da ISO (iso.org); a nota técnica e legal do IBGE em si; o cadastro de
  saúde CNES; as listas estaduais de postos de bombeiros e polícia; a licença e a lista de classes do MapBiomas; a
  cobertura do Google Open Buildings no Brasil; contagens da Overture por estado; as
  populações de Trindade e Martim Vaz. (A segunda verificação, abaixo, abriu depois a nota do IBGE, o cadastro CNES e o
  README e a legenda do MapBiomas.)

### Segunda verificação, de 18 a 24 de novembro de 2026

- **Aberto:** a camada estadual do IBGE em resolução completa `BR_UF_2022.zip` e a `regiao-limitrofe` das 27 unidades na
  API de malhas; a nota de limites do IBGE (Notas metodológicas 01/2025, CC BY 4.0); a pasta da BC250 de 2025 e seus
  termos de 2019; as pastas, o dicionário de dados e o arquivo do Acre do CNEFE 2022 do IBGE; o arquivo Localidades do
  Brasil 2022 do IBGE; o guia de endereços e a página de atribuição da Overture; os arquivos de fontes brasileiras do
  OpenAddresses; as páginas do Google Open Buildings e do 2.5D Temporal; o repositório de contornos da Microsoft e o
  histórico da sua licença; o registro do ANADEM no OpenTopography; o registro STAC do TOPODATA no INPE; os metadados da
  BHO 6 e da BHAE da ANA, a página de dados abertos da ANA, e o item de dados abertos e o FeatureServer do SNISB; o
  README do kit de usuário e a legenda da Coleção 11 do MapBiomas; o arquivo completo do CNES e o arquivo de UBS; o
  conjunto de revendedores de combustível da ANP; o portal de dados abertos do estado de São Paulo e o arquivo das escolas
  estaduais; a página de licença e as camadas do GeoSampa; as páginas e camadas do DataGeo; o site do IGC; o guia de
  endereçamento dos Correios (v1.4), a página de endereçamento, a página "Tudo sobre CEP" e a página do DNE; o Decreto
  8.777/2016 e o Decreto 9.903/2019 (art. 4º); a Resolução CGINDA nº 2/2017; `engine/address_search.py`,
  `tools/build_addresses.py` e `tools/build_places.py` no `main`.
- **Medido:** as 27 caixas a partir do `BR_UF_2022.zip` e qual polígono define cada borda que mudou; linhas, coordenadas e
  contagens de São Paulo por tipo no CNES; contagens do SNISB para o Brasil e para São Paulo por órgão; linhas do CNEFE no
  arquivo do Acre (com `COD_UF` e `NV_GEO_COORD`) e no arquivo de coordenadas de São Paulo; contagens de Localidades para
  São Paulo; as contagens do OSM de São Paulo em "São Paulo em detalhe" (Overpass, dados de 18 de novembro de 2026) e os
  tipos de `amenity=shelter` (um segundo servidor Overpass, dados de 1º de junho de 2026); os testes do analisador de
  endereços e do buscador de lugares.
- **Só busca:** a página de termos do MapBiomas (CC BY-SA); os totais nacionais do CNEFE; a contagem nacional de escolas
  do INEP (cerca de 226 mil).
- **Não verificado:** uma declaração de licença do IBGE nos arquivos do CNEFE ou de Localidades; a página de termos do
  MapBiomas em si; se o catálogo nacional de escolas do INEP tem coordenadas; as licenças por conjunto no `dados.gov.br`
  (a API exige token); o art. 1º do Decreto 8.777/2016 (o site derrubou a conexão); os sites do Corpo de Bombeiros e das
  polícias do estado; S2iD e Cemaden; um modelo de relevo estadual de São Paulo; a acurácia vertical do ANADEM; a
  cobertura do Google Open Buildings no Brasil; como a Overture escreve os CEPs brasileiros; a cobertura de endereços do
  OSM em São Paulo (a contagem de `addr:housenumber` na Overpass deu timeout); contagens de pontos de ajuda além de São
  Paulo.
