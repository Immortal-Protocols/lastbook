## O que este PR altera

<!-- Uma ou duas frases objetivas. Vincule a issue, se houver. -->

## Como foi verificado

<!-- Testes executados, builds e capturas de tela para alterações visuais (modos claro e escuro). -->

## Lista de verificação

- [ ] Os testes unitários passam (`python3 -B -m unittest app.tests.test_bridge app.tests.test_setup app.tests.test_data_folder app.tests.test_what_ships app.tests.test_update app.tests.test_address_search app.tests.test_topic_search app.tests.test_validate_topics app.tests.test_libq`).
- [ ] Nenhum novo acesso à rede: nenhuma porta aberta, socket, endereço web em `web/`, telemetria, checagem automática de atualização ou novo host não aprovado. Uso de rede somente via `engine/setup/download.py`.
- [ ] Nenhum dado pessoal ou residencial: sem regiões privadas, coordenadas residenciais, nomes de usuário/máquina, endereços de rede local, chaves ou tokens.
- [ ] Alterações nos guias citam páginas reais da biblioteca e `tools/validate_topics.py` passa.
- [ ] Qualquer nova dependência funciona offline e foi listada em `THIRD_PARTY_NOTICES.md` com sua licença.
