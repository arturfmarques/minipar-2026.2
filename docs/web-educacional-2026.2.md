# Ambiente educacional da Web MiniPar 2026.2

A interface educacional está em **http://127.0.0.1:5000/educacional**. A IDE de
desenvolvimento continua em `/`; o menu terminal continua em `python main.py`.
As duas páginas Web rodam no mesmo servidor Flask e usam o mesmo compilador
Python. A IDE antiga mantém sua API e seu fluxo de compilação/execução; a nova
página apresenta cada fase com dados estruturados e trabalhos isolados.

## Como iniciar

Na raiz do repositório:

Crie `.venv` e instale as dependências conforme o [README](../README.md).
O ambiente antigo de auditoria não é distribuído.

```powershell
.\.venv\Scripts\python.exe app.py
```

G++ C++20 deve estar disponível como no [diagnóstico](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/diagnostico-2026.2.md).
O servidor de desenvolvimento fica restrito a `127.0.0.1:5000` por padrão.
O cabeçalho compacto **MiniPar 2026.2** apresenta o seletor **IDE | Educacional**
nos dois ambientes. A fonte e o nome do arquivo são preservados ao alternar
na mesma aba via sessionStorage, consumido uma única vez. Resultados exigem
nova análise/compilação. A etapa 2/5 simplificou o estilo mantendo o backend:
[relatório de integração, testes e limites](web-integrada-2026.2.md).

## Pipeline e organização

`app.py` registra o Blueprint de `educational_web.py`, responsável por rotas,
arquivos e subprocessos. `src/educational_pipeline.py` importa as classes
**já existentes**: `Lexer`, `Parser`, `SemanticAnalyzer`, `TACGenerator` e
`CppCodeGenerator`. É uma fachada de leitura por etapa, sem outro lexer,
parser ou gerador intermediário. A geração C++ é `CppCodeGenerator.render`,
a mesma usada pelo terminal. A compilação emprega `toolchain.compile_command`
e `runtime_environment`, com o mesmo G++ configurado.

O semântico registra os símbolos dos escopos que visita em `scope_history`.
O serviço apresenta nome, categoria, tipo, escopo, linha e assinatura/metadados
reais. Parâmetros e variáveis de blocos não desaparecem da tabela ao sair
do escopo. Diagnósticos estruturados incluem fase, linha, coluna e mensagem.

`serialize_ast` percorre os campos dataclass da AST real, atribui IDs e
preserva arestas com nomes dos campos, tipo, localização e detalhes escalares.
O JSON contém **todos** os nós. `static/js/educacional.js` desenha a árvore
como SVG interativo: clique seleciona/expande, painel lateral mostra detalhes,
botões e roda do mouse ampliam, arrasto desloca e Centralizar reenquadra.
Nós profundos começam recolhidos. A vista limita 350 nós simultâneos;
**Entrar na subárvore** permite explorar os restantes sem perder dados.
O Teste 11 é maior que os demais e usa esse mesmo mecanismo.
O zoom mantém o ponto sob o cursor, a expansão conserva a posição do nó,
e um seletor de declarações facilita explorar árvores grandes. O painel
oferece acesso à localização do nó no fonte. O layout usa a paleta escura
da IDE, sem hero; o terminal recolhível abre ao compilar ou executar.

`templates/educacional.html` contém editor, barra de etapas, tabela/painéis,
entrada padrão e terminal integrado. `static/css/educacional.css` define
layout responsivo e contraste. `static/js/educacional.js` controla CodeMirror
5, requisições, fases, AST, tabelas, cópia e downloads. O editor preserva o
texto ao trocar de etapa, aceita tabulação, destaca MiniPar e numera linhas.
Diagnósticos marcam a linha e podem ser clicados. Se a CDN do CodeMirror estiver
indisponível, a edição e numeração continuam em `<textarea>` local; o destaque
nesse fallback fica indisponível.
Tokens podem ser filtrados por categoria sem alterar sua numeração original;
clique ou Enter localiza linha e coluna no editor. TAC e C++ também podem
ser baixados antes da compilação, usando o texto real retornado pela análise.

## Botões e API

| Botão | Rota | Resultado real |
|---|---|---|
| Tokens | `POST /api/educacional/analyze` (`stage=tokens`) | `Lexer.tokenize`, tabela tipo/lexema/linha/coluna, inclusive EOF. |
| AST | mesmo POST (`stage=ast`) | `Parser.parse` e árvore completa serializada. |
| Semântica | mesmo POST (`stage=semantic`) | `SemanticAnalyzer.analyze`, diagnósticos e símbolos. |
| TAC | mesmo POST (`stage=tac`) | `TACGenerator.generate_text` da AST aprovada. |
| C++ | mesmo POST (`stage=cpp`) | `CppCodeGenerator.render`, com linhas, destaque, copiar e baixar. |
| Compilar | `POST /api/educacional/compile` | Nova pasta de trabalho, `.tac`, `.cpp`, G++ e retorno. |
| Executar | `POST /api/educacional/jobs/<id>/run` | Processo nativo, stdin, stdout, stderr, código e tempo limite. |
| Baixar | `GET /api/educacional/jobs/<id>/files/<arquivo>` | C++, TAC, binário, `.arm` e SVG desta execução. |

`GET /api/educacional/examples` fornece o catálogo; `GET
/api/educacional/examples/<nome>` lê somente um arquivo do catálogo validado.
Os programas 1–11 são lidos de `tests/` sem cópias. Os exemplos curtos estão
em `examples/didaticos/` (aritmética, variáveis, condicionais, laços, funções,
classes e SEQ/PAR); os três Fork/Join existentes vêm de `examples/`.
Todos são fontes MiniPar editáveis; os sete arquivos didáticos novos foram
compilados/executados em testes nativos.

Cada botão de análise envia o **código atual** do editor. Se a fonte muda, o
painel anterior e o handle de compilação são invalidados. Falha léxica ou
sintática encerra as etapas posteriores; falha semântica impede TAC/C++/G++.
Uma exceção de backend retorna diagnóstico e não declara sucesso.

Compilar cria `output/educacional/<id>/` com `.minipar`, `.tac`, `.cpp`,
`job.json` e binário somente quando G++ retorna zero. O ID é aleatório de
128 bits; não reutilizamos arquivos antigos de outro trabalho. Executar cria
`runs/<id>/output/` dentro do trabalho. Duas execuções do mesmo binário têm
artefatos separados. O Teste 11 recebe `MINIPAR_ARM_OUTPUT` apontando para
o `.arm` dessa execução. O Teste 10 recebe `MINIPAR_OUTPUT_PREFIX` nessa pasta.
Os links só aparecem para arquivos realmente encontrados e permitidos.

O programa MiniPar do Teste 11 pode ser analisado com os botões acima:
essa é a **análise do compilador principal**. Depois de compilar, forneça uma
expressão em stdin e clique Executar. Tokens/AST/TAC/Assembly que aparecerem
no terminal integrado são a **saída do minicompilador escrito em MiniPar**.
O `.arm` anunciado fica disponível em Baixar. Essa página não monta nem
executa ARM no CPUlator: essa validação permanece **NÃO VERIFICADA**.

Para Fork remoto, o painel informa quando o AST contém esse destino. Inicie
um trabalhador externo com o binário e `--worker --port PORTA --workers N`,
nos endereços/portas do programa, antes de Executar. A UI não anuncia êxito
se o processo pai falhar por trabalhador ausente. Consulte o
[manual de runtime](runtime-2026.2.md). Um ensaio real da nova API compilou
o exemplo remoto, executou sem worker e obteve retorno 1 e `success=false`:
[evidência de falha esperada](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/web-educacional-remote.json).

## Limites e segurança local

O editor aceita até 200 kB de código e 16 kB de stdin. Compilação nativa tem
limite de 120 s; execução, 30 s. stdout/stderr são drenados enquanto o processo
roda e apenas os primeiros 64 KiB por fluxo são exibidos, com indicação de
truncamento. Em timeout, o serviço tenta encerrar a árvore do processo. Cada
arquivo para download deve ter no máximo 20 MB. Caminhos de exemplos são
chaves de catálogo; caminhos de download passam por lista permitida,
normalização e verificação de que permanecem no trabalho. Sem `shell=True`.
As rotas antigas de arquivos MiniPar também rejeitam nomes com separadores,
drives ou caracteres de controle. Arquivos válidos conservam suas respostas.

Trabalhos dessa interface com mais de 24 horas são removidos ao criar outro
trabalho; a limpeza exige ID válido e `job.json` e só opera dentro de
`output/educacional`. Esse diretório está sob o `output/` ignorado pelo Git.
Artefatos das outras interfaces e referências não são tocados.

**Não existe sandbox de segurança para C++ arbitrário**. Limites de tempo,
pastas separadas e localhost não impedem acesso do binário ao sistema de
arquivos/rede do usuário. Use essa interface apenas localmente, com programas
confiáveis. Não publique o servidor nem o executor na rede pública.

## Testes e evidências

```powershell
.\.venv\Scripts\python.exe -m pytest tests/integration/test_educational_web.py -q
.\.venv\Scripts\python.exe -m pytest -q
node --check static/js/educacional.js
.\.venv\Scripts\python.exe tools/validate_educational_examples.py
```

Os testes da Web exercitam a rota original e a nova, catálogo sem cópias,
lexer e posições, AST completa do Teste 11, símbolos/diagnósticos, equivalência
de TAC/C++ com os geradores existentes, G++ real, stdout/stderr, timeout,
truncamento, downloads e proteção de caminhos. Os sete exemplos didáticos
foram compilados e executados de verdade. A regressão final também cobre
terminal, programas 1–11, Fork/Join, TCP, Mandelbrot e Sierpinski.
`tools/validate_educational_examples.py` executou os Testes 8–10 pela nova
API, aplicou os oráculos existentes e conferiu os downloads:
[resultado por programa](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/web-educacional-8910.json).
Uma consulta HTTP ao servidor Flask real retornou 200 para as duas páginas,
catálogo, JavaScript e CSS, e 404 para um caminho de exemplo indevido:
[registro HTTP](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/web-educacional-http.json).

Evidências de pytest: [análise inicial](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/pytest-educacional-initial.xml),
[compilação/execução](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/pytest-educacional-native.xml),
[exemplos](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/pytest-educacional-exemplos.xml) e
[suíte completa final](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/pytest-educacional-validado.xml).
Na validação original do laboratório, **432/432 testes passaram em 428,78 s**; a
[comparação com a suíte anterior](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/regressao-web.json) preserva os
413 casos anteriores e registra os 19 adicionais, sem skips ou xfails.

Na primeira tentativa do validador 8–10, o Teste 8 passou, mas o Teste 9
interrompeu com `IndexError: list index out of range` no oráculo que buscava
`MANDELBROT_BEGIN\n`. A API nova preservava `\r\n` do Windows, enquanto
`subprocess.run(text=True)` da interface antiga já entregava `\n`.
`_bounded_process` agora normaliza stdout/stderr textuais. A segunda execução
passou nos três programas. A primeira tentativa não foi contada como êxito.

A automação visual daquela etapa **NÃO FOI EXECUTADA**: a ferramenta de navegador
não iniciou seu runtime Node (`The system cannot find the path specified`).
Não há captura de tela atribuída a esta etapa. As respostas HTTP, testes de
JavaScript e API não substituem uma inspeção de legibilidade, zoom/arrasto
e uso em tamanhos diferentes de janela; estes pontos ficam pendentes para
uma execução real em navegador.

Os resultados posteriores da integração das duas interfaces, incluindo uma
nova tentativa de inspeção visual, estão no [relatório da etapa 2/5](web-integrada-2026.2.md).
