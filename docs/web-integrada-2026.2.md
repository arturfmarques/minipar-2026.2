# Web integrada MiniPar 2026.2 — etapa 2/5

Revisão de 11/11/2026. A IDE original e o ambiente educacional continuam no
mesmo `app.py`, com as mesmas rotas `/` e `/educacional`, em
`http://127.0.0.1:5000`. O Blueprint educacional, os serviços e o compilador
não foram alterados nesta etapa.

## Referência e decisões

Foram examinados, somente para leitura, `templates/index.html`,
`templates/didatico.html`, `static/css/style.css`, `static/css/didatico.css`,
`static/js/script.js` e `static/js/didatico.js` do projeto
`C:/GitHub/MiniPar-Referencia-Colega`. A referência organiza o ambiente em
cabeçalho compacto, editor e resultados lado a lado, abas de fases, filtros
de tokens e árvore SVG com D3. Aproveitamos os conceitos de organização e
filtro, sem copiar arquivos completos, importar D3 ou substituir nossa AST.

| Aspecto | Adaptação neste projeto |
| --- | --- |
| Identidade e navegação | Um cabeçalho Jinja compartilhado, MiniPar 2026.2 e seletor IDE / Educacional com modo atual destacado |
| Organização | Editor à esquerda, resultados à direita, mesma paleta escura da IDE, fontes locais |
| Elementos removidos | Hero, marca decorativa, introduções repetidas, rodapé técnico e cartões de estado duplicados |
| Etapas | Botões diretos; somente fases realmente executadas aparecem no resumo |
| Tokens | Filtro único por categoria, contagem, número original, lexema e linha/coluna; clique ou Enter localiza no editor |
| Semântica | Tabela de nome, categoria, tipo, escopo e metadados reais, com diagnósticos separados |
| TAC e C++ | Código numerado, destaque, cópia e download do conteúdo real mesmo antes de compilar |
| Entrada e saída | Stdin compacto; terminal recolhível que abre ao compilar ou executar |

Nenhum crédito legítimo foi removido. Não foram identificadas marcas
decorativas de IA que exigissem remoção específica. A referência foi lida
no disco; sua interface não foi executada em navegador nesta etapa.

O PDF oficial do professor não está disponível em `referencias/` após a limpeza
anterior. Portanto, não se declara nova conferência direta das páginas 45–47.
As etapas didáticas foram preservadas conforme a solicitação e o diagnóstico.

## Navegação e preservação da fonte

Os links permanecem na mesma aba, origem e porta. `web-common.js` transfere
somente fonte e nome simples do arquivo via `sessionStorage` ao clicar no
outro modo. O destino consome esse rascunho uma única vez. Não há sincronização
contínua, banco de dados ou dependência nova. Conteúdo inválido é descartado;
storage bloqueado permite a navegação normal, sem preservação da fonte.
Cliques com modificadores ou botão do meio seguem o comportamento do navegador.

Resultados de análise, entrada, trabalhos compilados e sessões não são
transferidos. A página de destino exige nova análise/compilação. A IDE mantém
carregamento, edição, C++, TAC, Terminal Output, sessões e seus endpoints.
As duas interfaces continuam consumindo os arquivos dos programas 1–11.

## AST

Foi mantido o desenho SVG próprio e seu modelo de recolhimento/subárvores.
`educacional-view.js` separa apenas cálculos de apresentação testáveis:
geometria, categorias de tokens e transformação de zoom. Não contém parser
nem constrói AST alternativa.

- Nós com tipo, aresta e valor/nome abreviado; tooltip e painel conservam o
  detalhe integral e a localização. Seleção também por Enter ou espaço.
- Zoom sob o cursor e no centro pelos botões; arrasto, Centralizar, Voltar,
  Recolher e Entrar na subárvore continuam disponíveis.
- Expansão preserva a posição do nó selecionado; centralização respeita a
  área disponível e evita reduzir inicialmente a árvore a texto minúsculo.
- Seletor de declarações facilita acessar funções/classes distantes e
  botão Ir para o fonte usa linha e coluna reais.
- Árvores extensas começam recolhidas; o limite existente de expansão de
  350 nós por vista orienta a entrada em subárvores. O JSON completo não é
  truncado. A árvore real do Teste 11 é usada nos testes de geometria.
- Observadores de tamanho são descartados ao trocar fonte ou etapa.

Os testes verificam ausência de interseção entre retângulos da geometria
calculada. Isso não substitui uma inspeção da renderização, fontes e gestos
num navegador real.

## Arquivos desta etapa

Alterados: `templates/index.html`, `templates/educacional.html`,
`static/js/script.js`, `static/js/educacional.js`, `static/css/educacional.css`,
`README.md`, `docs/web-educacional-2026.2.md`, `docs/diagnostico-2026.2.md` e
inventário `docs/conteudo-github.txt`.

Novos: `templates/_web_header.html`, `static/css/web-common.css`,
`static/js/web-common.js`, `static/js/educacional-view.js`,
`tests/integration/test_web_unified.py`, `tests/web/unified-web.test.cjs`,
este relatório e evidências identificadas por `web-integrada`.

`app.py`, `educational_web.py`, `src/`, BNF, programas MiniPar e testes anteriores
foram preservados. Não houve commits, push, mudanças de arquitetura ou avanço
para a etapa 3/5.

## Reprodução

Ferramentas verificadas: Python 3.14.3, Flask 3.0.0, pytest 9.2.0,
Node v24.14.1 e G++ MSYS2 16.2.0. Node executa os testes de apresentação
com seu runner nativo; não é necessário para servir ou utilizar a aplicação.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.lock.txt
$env:MINIPAR_CXX = 'C:\msys64\mingw64\bin\g++.exe'
.\.venv\Scripts\python.exe app.py
```

Abra `http://127.0.0.1:5000/` ou `http://127.0.0.1:5000/educacional` e use o
seletor. Somente esse servidor deve ser iniciado. Execute programas confiáveis,
conforme as restrições já documentadas do servidor local.

Com G++ e Node no PATH, a suíte completa continua com um comando:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

O teste Python produz a fixture com Lexer/Parser reais e chama `node --test`.
Se Node estiver ausente, somente esse teste é explicitamente marcado skip;
isso não equivale a validar os controles no navegador.

Na execução desta etapa foi usado um venv temporário fora do repositório,
`%TEMP%/minipar-web-20261111`, instalado com o mesmo lock. Os comandos reais
de pytest usaram `-q -p no:cacheprovider`, `--basetemp` externo e
`--junitxml output/validacoes/pytest-web-integrada-*.xml`.
Os alvos executados foram, na ordem:

```text
python -m pytest tests/integration/test_web_unified.py tests/integration/test_educational_web.py
python -m pytest tests/integration/test_web_unified.py
python -m pytest
node --check static/js/web-common.js
node --check static/js/educacional-view.js
node --check static/js/educacional.js
node --check static/js/script.js
node --check tests/web/unified-web.test.cjs
```

O servidor Flask temporário foi encerrado e o venv temporário foi removido
após as verificações. Nenhum ambiente do usuário foi removido.

## Validação e limitações

Primeira execução dirigida: **25 aprovados e 1 falhou**. Os testes novos de
geometria receberam a tupla `(raiz, contagem)` de `serialize_ast` como se fosse
a raiz. A fixture foi corrigida para usar o primeiro elemento, mantendo as
asserções e o contrato do compilador. A repetição dos sete testes novos
aprovou todos, incluindo as dez verificações JavaScript. As evidências
iniciais foram mantidas.

O novo teste nativo percorre Tokens, AST, Semântica, TAC e C++, compila com G++,
baixa C++/TAC/executável, recebe `8` em stdin e verifica saída `64` de uma tarefa
Fork/Join fixada em uma CPU disponível. Os testes anteriores cobrem erros,
classes, canais, execução local/remota e programas reais. Os novos testes de
catálogo comparam os conteúdos dos onze programas nas duas APIs.

A regressão completa aprovou **481 testes em 466,76 s**, sem falhas, erros,
skips ou xfails. A comparação por nome e classe conserva os **474 casos
anteriores** e acrescenta sete. Um desses sete executa **dez testes JavaScript**;
eles não são somados novamente à contagem do pytest.

Consultas HTTP ao servidor real retornaram **200** para as duas páginas,
os dois catálogos e os cinco novos/alterados assets consultados. A auditoria
de hashes, repetida após a suíte, confirmou **85 arquivos protegidos do
projeto** e **81 arquivos da referência** sem alterações. `HEAD` permaneceu
`36e25fc6234c95fd60cdadebd7ec22c65c5d7657`. `git diff --check` não apontou erros;
há avisos já existentes da conversão LF/CRLF do Git no Windows.
O [inventário publicável](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/conteudo-github.txt) lista **298 arquivos**.
A [simulação de git add](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/git-add-web-integrada-dry-run.txt) retornou
zero; não foi executado `git add` efetivo.

| Evidência | Conteúdo |
| --- | --- |
| [pytest inicial](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/pytest-web-integrada-inicial.xml) | 25 aprovados e a falha real da fixture |
| [repetição dirigida](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/pytest-web-integrada-segundo.xml) | Sete testes novos aprovados |
| [pytest completo](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/pytest-web-integrada-final.xml) | 481 aprovados |
| [regressão](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/regressao-web-integrada.json) | 474 preservados, sete novos, nenhum ausente |
| [JavaScript](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/web-integrada-js.json) | Dez testes reais de navegação, filtros e geometria |
| [auditoria](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/web-integrada-auditoria.json) | HTTP, sintaxe JavaScript, hashes e bloqueio visual |
| [snapshot inicial](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/preservacao-web-integrada-inicio.json) | Hashes anteriores às alterações |

Os testes anteriores regravaram suas evidências usuais de runtime,
afinidade e programas 1–10; os resultados foram mantidos, removendo somente
metadados locais de perfil/hostname para publicação. O primeiro erro desta
etapa continua no JUnit inicial, sem ser contado como aprovação.

**Inspeção visual pendente:** o inventário CUA retornou
`The browser access host is unavailable`. A alternativa nativa no Chrome
interrompeu duas tentativas de abrir uma aba por detectar entrada do usuário
na janela (`user input was detected in this window`). Nenhuma página MiniPar
foi observada nesse navegador. Não há aprovação visual em 1366×768 ou
1920×1080, nem alegação de testes manuais de cliques, arrasto, clipboard ou
downloads em navegador. HTML, JavaScript e APIs foram verificados separadamente.

O CodeMirror continua vindo da CDN existente; na educacional há fallback de
textarea. Linux, duas máquinas físicas e CPUlator permanecem nas condições
e pendências das etapas anteriores; esta revisão visual não os valida.
