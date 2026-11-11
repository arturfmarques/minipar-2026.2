# Teste 11 — revisão de fidelidade e demonstração (etapa 3/5)

Revisão de 11/11/2026. O minicompilador permanece implementado em
`tests/teste11_minicompilador_armv7.minipar`. O compilador principal gera
C++20, G++ produz o executável, e esse executável analisa a expressão e
escreve o ARM. Os validadores Python não substituem nenhuma dessas fases.

## Materiais examinados diretamente

Os três PDFs foram encontrados em `Downloads`, lidos com pypdf e renderizados
com PyMuPDF. Todas as páginas foram inspecionadas: Java, duas páginas; exemplo
ARM, uma página; saída de referência, uma página. Os arquivos e suas extrações
existentes não foram alterados. Hashes e contagens constam em
[materiais](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/teste11-etapa3-materiais.json).

Os PDFs apresentam código/saída em texto com linhas agrupadas pelo layout;
o arquivo chamado `Execucao-Saida-okRodounoCPULATOR.pdf` mostra a saída do
minicompilador e o resultado 22, sem uma captura de registradores do simulador.
Seu nome não é evidência de execução do nosso código. O enunciado específico
do Classroom foi considerado conforme a reprodução enviada pelo usuário;
nenhum acesso ao Classroom foi realizado.

Também foram examinados, somente para leitura, o fonte
`tests/teste11/teste11_minicompilador.minipar`, `tests/test_teste11.py` e os
arquivos ARM do projeto do colega. A organização de sua demonstração separa
três arquivos, inclusive a expressão repetida. Nosso validador já fazia essa
separação; nenhum arquivo ou gerador do colega foi copiado.

## Comparação com a referência Java

| Etapa | Referência oficial | Implementação MiniPar preservada |
| --- | --- | --- |
| Lexer | Regex, números, identificadores, operadores e parênteses | Percurso de caracteres, tokens tipados com localização e diagnóstico de caracteres inválidos |
| Parser | Descida recursiva: expressão, termo e fator | Mesma precedência e associatividade; valida fechamento de parênteses e consumo até EOF |
| AST | Impressão lateral, filho direito acima | Árvore com ROOT/L/R, tipos e filhos explícitos; mesma estrutura das expressões obrigatórias |
| TAC | Pós-ordem, temporários t1… | Pós-ordem dinâmica; os quatro comandos da primeira expressão correspondem ao anexo |
| Símbolos | CONST/VAR em HashMap | CONST deduplicadas e VAR com estado/valor; ordem de primeira ocorrência |
| Avaliação | double; variável indefinida vira zero com aviso | number; variável indefinida e divisão por zero são erros |
| ARM | Registradores crescentes; primeira expressão termina em r8 | Registradores reutilizados, pilha própria; resultado conhecido em r0 |
| Arquivo | Java apresentado imprime o Assembly | MiniPar também grava o texto em `.arm` e anuncia `ARQUIVO:` |
| Divisão | Emite comentário de operação não suportada | Rotina inteira já existente foi preservada; não houve expansão de recursos |

O Java reconhece `=` e comentários no lexer, mas não implementa atribuição no
parser apresentado. Nosso minicompilador não aceita atribuições nem comentários
na expressão; isso não afeta as três entradas obrigatórias. Comentários `#`
permanecem válidos no programa MiniPar hospedeiro. Não foi necessário alterar
BNF, Lexer, Parser, semântica, TAC ou runtime do compilador principal.

Os formatos de impressão e os registradores diferentes não mudam a semântica.
O gerador atual evita esgotar registradores, inicializa sua pilha e carrega
constantes com `ldr =valor`. Não foi criado modo especial para colocar 22 em r8.
As extensões previamente testadas (unários, variáveis definidas por API e
divisão inteira ARM) foram mantidas, sem novos recursos.

## Execução nativa e arquivos novos

Foi executado o validador existente com relatório separado para esta revisão:

```powershell
python tools/validate_minicompiler.py --report output/validacoes/teste11-etapa3/validacao.json
```

| Execução | Entrada | Resultado / r0 assinado | r0 hexadecimal | Arquivo |
| --- | --- | ---: | --- | --- |
| 1 | `((2+4)*7)-(5*4)` | 22 | `00000016` | [expressao-1.arm](evidencias/teste11/expressao-1.arm) |
| 2 | `((10-8*7)+4)*2` | -84 | `FFFFFFAC` | [expressao-2.arm](evidencias/teste11/expressao-2.arm) |
| 3 | `((2+4)*7)-(5*4)` | 22 | `00000016` | [expressao-3.arm](evidencias/teste11/expressao-3.arm) |

As três execuções são processos nativos distintos, com nomes de saída distintos.
Os arquivos 1 e 3 são iguais porque a expressão é igual; ambos foram gerados
novamente pelo executável. A expressão 2 tem AST, TAC e Assembly diferentes.
O mesmo validador aprovou ainda os cinco casos adicionais já existentes.

O [JSON de validação](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/teste11-etapa3/validacao.json) registra build,
comandos, retornos, seções internas, montagem Zig/LLVM e emulação Unicorn
Cortex-A9. As saídas completas são `expressao-N.txt` nessa mesma pasta.
Esses testes não são apresentados como equivalentes ao CPUlator.

## CPUlator efetivamente utilizado

As três entradas obrigatórias foram verificadas no navegador Chrome, por CUA
nativo, no sistema ARMv7 DE1-SoC. Cada `.arm` local foi aberto, montado com o
GNU assembler do próprio CPUlator (**Compile succeeded**) e executado por
Continue/Stop até o laço `__expr_done`. Foram observados:

| Arquivo | r0 | r12 | sp | pc | Resultado |
| --- | --- | --- | --- | --- | --- |
| expressao-1.arm | 00000016 | 00000000 | 00010060 | 00000054 | 22 |
| expressao-2.arm | FFFFFFAC | 00000000 | 00010060 | 00000054 | -84 |
| expressao-3.arm | 00000016 | 00000000 | 00010060 | 00000054 | 22 |

O [registro de observação](evidencias/teste11/cpulator.json) contém
identificação dos arquivos por hash, mensagens de montagem, configuração e
valores observados. As imagens reais foram exibidas pelas ferramentas durante
a inspeção, mas não foram exportadas como PNG para o repositório. As capturas
acadêmicas definitivas deverão ser feitas conforme o roteiro abaixo.

Na primeira carga do caso 2, sem reiniciar a página, o simulador manteve o
`sp=00010060` anterior e emitiu avisos de acesso a espaço de pilha não alocado
durante o carregamento do ELF, antes de executar. O resultado ainda foi -84.
O caso foi repetido após recarregar a página e confirmar `pc=sp=0`: montagem
e execução sem esses avisos, com o mesmo resultado. Essa observação sugere
interferência do estado da execução anterior na recarga; não se atribui o
aviso ao gerador sem evidência. A ocorrência está registrada no JSON e não
foi ocultada. Nenhuma verificação de depuração foi desativada.

O acesso direto à ferramenta de abas continuou indisponível
(`The browser access host is unavailable`), mas o controle nativo do Chrome
permitiu executar esta validação. **CPUlator: APROVADO para os três casos
registrados**, separadamente da validação Zig/LLVM e Unicorn. Não se afirma
validação CPUlator de todas as expressões adicionais ou de placa física.

## Alterações e regressão

Não foi encontrado defeito que exigisse mudar o fonte MiniPar ou o gerador ARM.
Foram preservados compilador principal, BNF, runtime, interfaces e testes 1–10.
O único ajuste em código existente foi a descrição do escopo em
`tools/validate_minicompiler.py`: o relatório não presume mais que o navegador
esteja indisponível. Seu campo `cpulator` descreve apenas o que o validador CLI
não executa; a comprovação no navegador está no JSON separado acima.

Novo teste: `tests/integration/test_minicompiler_delivery.py`. Compila a
aplicação real, coloca conteúdo anterior inválido no destino, executa as três
entradas obrigatórias e `6*9-1`, confere regravação, monta e emula cada arquivo.
Confirma repetição idêntica e Assembly diferente para entradas diferentes.
As respostas esperadas são oráculos de teste, não resultados embutidos no
minicompilador. Nenhum teste anterior teve sua expectativa alterada.

```powershell
python -m pytest -q -p no:cacheprovider --basetemp "$env:TEMP/minipar-teste11-etapa3-pytest" --junitxml output/validacoes/pytest-teste11-etapa3.xml
```

Resultado: **482 aprovados em 499,72 s**, sem falhas, erros, skips ou xfails.
Os **481 anteriores** permanecem, com um novo caso. Evidências:
[JUnit](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/pytest-teste11-etapa3.xml),
[comparação](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/regressao-teste11-etapa3.json) e
[preservação](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/preservacao-teste11-etapa3-final.json).
Foram comparados 93 arquivos existentes do projeto: somente a descrição do
validador mudou. Os 81 arquivos da referência e os três PDFs oficiais mantêm
seus hashes. Os testes regravaram suas evidências usuais; somente metadados
locais de perfil e hostname foram removidos para publicação.

Ferramentas: Python 3.14.3, G++ MSYS2 16.2.0, pytest 9.2.0, Zig/LLVM via
ziglang 0.17.1, Unicorn 2.1.4 e pyelftools 0.33. pypdf 7.0.1 e PyMuPDF 2.1
foram usados somente para ler os PDFs, fora das dependências do projeto.
Foi criado um venv temporário em `%TEMP%/minipar-teste11-20261111` e instalado
com `pip install -r requirements-dev.lock.txt pypdf pymupdf`. A regressão usou
esse Python e `PYTHONDONTWRITEBYTECODE=1`. Não houve execução do Java: a
comparação é de código/saída oficial, não uma alegação de teste Java nativo.
O ambiente temporário foi removido ao final; nenhum venv do usuário foi
alterado. Extrações e renderizações dos PDFs ficaram somente em
`output/revisao-teste11-pdfs/`, ignorado pelo Git, sem republicar os anexos.

Arquivos desta etapa: o validador mencionado, o novo teste, este guia,
`docs/teste11-minicompilador.md`, `docs/diagnostico-2026.2.md`, `README.md`,
o inventário `docs/conteudo-github.txt` e as evidências da etapa 3.
Não houve commits, push ou avanço para a etapa 4/5.
O inventário lista **324 arquivos publicáveis**. `git diff --check` e a
[simulação de git add](https://github.com/arturfmarques/MiniPar-2026.2/blob/0112d1afdb395a6b6769d1c35f76ebdb83337e03/docs/evidencias/git-add-teste11-etapa3-dry-run.txt) retornaram
zero, sem staging efetivo. O `HEAD` permanece
`36e25fc6234c95fd60cdadebd7ec22c65c5d7657`.

## Reprodução na apresentação

Na raiz, com as dependências e G++ já configurados:

```powershell
python -m pip install -r requirements-dev.lock.txt
python main.py tests/teste11_minicompilador_armv7.minipar
$env:PATH = 'C:\msys64\mingw64\bin;' + $env:PATH
$env:MINIPAR_ARM_OUTPUT = 'output/apresentacao-expressao-1.arm'
'((2+4)*7)-(5*4)' | .\output\teste11_minicompilador_armv7.exe
$env:MINIPAR_ARM_OUTPUT = 'output/apresentacao-expressao-2.arm'
'((10-8*7)+4)*2' | .\output\teste11_minicompilador_armv7.exe
$env:MINIPAR_ARM_OUTPUT = 'output/apresentacao-expressao-3.arm'
'((2+4)*7)-(5*4)' | .\output\teste11_minicompilador_armv7.exe
Remove-Item Env:MINIPAR_ARM_OUTPUT
```

Também é possível iniciar o executável sem pipe e digitar a expressão no prompt.
Os blocos TOKENS, AST, SIMBOLOS, TAC e ARM são produzidos pela aplicação MiniPar.
O C++ e TAC do programa inteiro, em `output/`, são artefatos do compilador
principal e não devem ser confundidos com o TAC/ARM da expressão.

No [CPUlator ARMv7 DE1-SoC](https://cpulator.01xz.net/?sys=arm-de1soc):

1. Comece em uma página reiniciada do simulador, com `pc` e `sp` zerados.
2. Use **File → Open** (Ctrl+O) para abrir o `.arm`. O filtro padrão é S File;
   digite o caminho completo ou selecione todos os arquivos. Não precisa renomear.
3. Use **Compile and Load (F5)** e aguarde **Compile succeeded**.
4. Execute **Continue (F3)** e depois **Stop (F4)** quando chegar ao laço
   `__expr_done`. Pode também marcar breakpoint ali antes de continuar.
5. Confira `r0` conforme a tabela, `r12=0` e `pc` no laço final.
   `FFFFFFAC` representa -84 em inteiro assinado de 32 bits.
6. Recarregue a página pelo botão do navegador antes de carregar a próxima
   expressão, mantendo as verificações de depuração ativas. Isso é diferente
   de Restart/Reload na barra do CPUlator, que pode manter registradores.

O procedimento corresponde ao fluxo da
[documentação oficial do CPUlator](https://cpulator.01xz.net/doc/): abrir fonte,
montar/carregar e executar/depurar. A diretiva `.syntax unified` já está no ARM.
O laço final é intencional: não há saída textual do programa Assembly.

## Capturas para o relatório acadêmico

Para cada uma das três execuções, faça capturas reais com identificação do caso:

1. Terminal: comando/entrada, TOKENS, AST, SIMBOLOS e TAC da expressão.
2. Terminal: RESULTADO, caminho `ARQUIVO:` e STATUS APROVADO.
3. CPUlator: nome do arquivo no Editor e início do Assembly gerado.
4. CPUlator: **Compile succeeded**, Disassembly em `__expr_done` e painel de
   registradores mostrando `r0`, `r12`, `sp` e `pc` após a execução.

Se não couber tudo, use capturas complementares. A repetição deve ter seu
próprio arquivo e registro. Não use imagens do colega ou do professor como
evidência desta implementação e não edite os registradores para obter a saída.
