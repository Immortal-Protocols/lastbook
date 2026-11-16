# Contribuindo com o Último Livro (Lastbook)

Obrigado por ajudar. Este projeto é a adaptação brasileira do **Lastbook** (<https://github.com/Immortal-Protocols/lastbook>, <https://lastbook.org>) e foi feito para o dia em que não houver internet — portanto, o mais importante é que funcione offline, permaneça correto e nunca envie dados para lugar nenhum.

## Configuração do ambiente

1. Clone o repositório e crie um ambiente virtual com Python 3.11 ou superior.
2. Instale as dependências da sua plataforma: `packaging/requirements_macos.txt` (macOS) ou `packaging/requirements_app.txt` (Windows).
3. Obtenha uma pasta de dados (`LastbookData`): execute `python3 app/main.py` e deixe a configuração baixar o pacote Small, ou descompacte um pacote de <https://lastbook.org>. Aponte o aplicativo para ela com `--data` ou `LASTBOOK_DATA`.

O [README.md](README.md) explica a estrutura do projeto e como compilar os aplicativos.

## Testes

```bash
python3 -B -m unittest app.tests.test_bridge app.tests.test_setup app.tests.test_data_folder app.tests.test_what_ships app.tests.test_update app.tests.test_address_search app.tests.test_topic_search app.tests.test_validate_topics app.tests.test_libq
```

Execute os testes acima antes de abrir um pull request (`test_topic_search` requer `node` no `PATH` e é ignorado sem ele). Se você alterar o empacotamento, execute também o build da sua plataforma: ele termina com uma varredura de pacote que precisa passar. Se alterar um guia em `content/`, rode `tools/validate_topics.py` contra uma biblioteca real para garantir que cada `id`, página e caminho de enciclopédia citado ainda exista:

```bash
python3 tools/validate_topics.py --data /caminho/para/LastbookData   # ou defina LASTBOOK_DATA
```

O script lê os arquivos da biblioteca diretamente, sem precisar de servidor. `tools/libq.py` aceita o mesmo `--data` para localizar e ler a página exata que você deseja citar: `python3 tools/libq.py --data /caminho/para/LastbookData search "boil water"`.

## Regras que mantêm o projeto fiel à sua proposta

**Sem rede.** O aplicativo não abre porta de escuta nem faz conexões, com duas exceções — ambas iniciadas pela própria pessoa e ambas passando por `engine/setup/download.py` apenas para os hosts em `ALLOWED_HOSTS`: os downloads da tela de configuração e o botão *Verificar atualizações* (`engine/update.py`, somente `downloads.lastbook.org`).

- Nada de telemetria, analytics, envio de relatórios de falha, fontes ou scripts carregados da web ou qualquer comunicação oculta. A verificação única de atualização (`engine/update.py`) só roda quando alguém clica no botão e apenas informa se existe versão mais nova.
- Nossas próprias páginas em `web/` não contêm endereços web externos (`https?://`). O build falha se houver algum.
- Qualquer nova dependência deve funcionar totalmente offline, sem abrir sockets nem iniciar servidores. Informe no pull request o que ela é, sua licença e por que é necessária, e adicione-a ao [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
- O executor da IA local permanece sem sockets: sem backend RPC, sem servidor HTTP e sem código de download.

**Linguagem geral, sem dados pessoais ou residenciais.** O Lastbook original começou como uma biblioteca doméstica. Os guias distribuídos usam termos gerais, e nada compartilhado pode citar casas reais, ruas, coordenadas, máquinas ou contas pessoais.

- Escreva guias pensando em qualquer leitor. Só cite uma região quando a fonte ou adaptação tratar especificamente daquela região.
- Nunca faça commit de `web/home-area.json`, listas privadas de palavras, coordenadas reais de residências, nomes de usuário/máquina, endereços de rede local, chaves ou tokens. Caminhos em testes e exemplos usam marcadores genéricos como `/caminho/para/LastbookData` ou `C:\Users\you\app-test`.
- Para manter seus próprios termos fora de um build local, coloque-os em uma cópia local de `packaging/ship_edits.json` (`forbidden`) sem incluí-la em commits.

**Fontes em primeiro lugar.** Cada cartão de guia aponta para uma página real de uma fonte real na biblioteca, com seu número de página. Se a biblioteca não cobrir algum assunto, registre em `content/gaps.json` em vez de escrever orientações de memória.

**Palavras simples.** O texto da interface deve ser curto, concreto e sereno. Muitos leitores estarão estressados, cansados ou consultando em uma situação de urgência.

## Pull requests

- Mantenha cada alteração pequena e focada em um assunto, explicando o que foi testado e como.
- Capturas de tela ajudam em qualquer mudança visual, nos modos claro e escuro (macOS, Windows e Linux quando possível).
- Esteja pronto para explicar qualquer alteração que toque em configuração (`engine/setup/`), ponte (`app/bridge.py`), varreduras de segurança ou no baixador (`download.py`). Esses pontos protegem as bibliotecas e a privacidade dos usuários.

## Reportando falhas de segurança ou privacidade

Não abra uma issue pública. Para questões ligadas ao projeto original Lastbook, envie e-mail para `hello@lastbook.org` com os detalhes encontrados e como reproduzir.

## Código de conduta

Todos os participantes seguem o [Código de Conduta](CODE_OF_CONDUCT.md).
