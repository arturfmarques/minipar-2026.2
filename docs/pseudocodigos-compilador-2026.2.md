# Pseudocódigos do compilador MiniPar 2026.2

Os procedimentos apresentam as etapas implementadas no compilador. Entradas e saídas seguem os contratos dos módulos Python; `nome()` corresponde ao método indicado em cada seção.

## 1. Analisador léxico

Fonte: [lexer.py](../src/lexer.py), classes `Lexer`, `Token`, `TokenType` e
`LexerError`; métodos `tokenize`, `_peek`, `_advance`,
`_skip_whitespace_and_comments` e `_make_token`.

Entrada: texto fonte. Saída: lista de tokens com tipo, lexema, linha e coluna,
terminada por END_OF_FILE; falha: LexerError com Diagnostic.

```text
TOKENIZE(fonte):
    tokens ← lista vazia; posição ← 0; linha ← 1; coluna ← 1
    enquanto posição < tamanho(fonte):
        SKIP_WHITESPACE_AND_COMMENTS()
        se terminou o fonte: sair do laço
        início ← (linha, coluna); caractere ← PEEK()
        se letra ou underscore:
            consumir letras, dígitos e underscores
            tipo ← KEYWORDS[lexema], ou IDENTIFIER se não reservado
        senão se dígito:
            consumir dígitos e, opcionalmente, ponto e novos dígitos
            tipo ← NUMBER
        senão se aspas duplas:
            consumir até o fechamento; decodificar escapes existentes
            se chegou ao fim sem fechamento: lançar LexerError(início)
            tipo ← STRING_LITERAL
        senão:
            reconhecer operador composto (incluindo ->), simples ou delimitador
            se não reconhecido: criar token UNKNOWN
        acrescentar Token(tipo, lexema, início) a tokens
    para cada token em tokens:
        se tipo = UNKNOWN: lançar LexerError(caractere inválido, localização)
    acrescentar END_OF_FILE com posição final
    retornar tokens

SKIP_WHITESPACE_AND_COMMENTS():
    enquanto houver caracteres:
        se espaço: ADVANCE()
        senão se PEEK() = '#': consumir até nova linha ou fim
        senão: retornar

ADVANCE():
    retirar caractere atual e avançar posição
    se nova linha: linha ← linha + 1; coluna ← 1
    senão: coluna ← coluna + 1
    retornar caractere retirado
```

O lexer não consulta a tabela de símbolos. `on` e `core` permanecem
IDENTIFIER, reconhecidos contextualmente pelo parser. Comentários dentro de
strings são texto. Não se acrescentou reconhecimento de comentários à AST.

## 2. Analisador sintático e AST

Fontes: [parser.py](../src/parser.py), `Parser`; [ast_nodes.py](../src/ast_nodes.py).
Entrada: tokens válidos com EOF final. Saída: Program com nós reais; falha:
ParseError. O construtor rejeita EOF ausente, UNKNOWN e tokens após EOF.

```text
PARSE():
    programa ← Program(statements = [])
    enquanto PEEK().type ≠ END_OF_FILE:
        comando ← PARSE_STATEMENT()
        se comando existe: programa.statements.adicionar(comando)
    retornar programa

CONSUME(tipo, descrição):
    se PEEK().type = tipo: retornar ADVANCE()
    lançar ParseError(descrição + token encontrado, linha e coluna atuais)

PARSE_STATEMENT():
    guardar token inicial para localização
    escolher produção pelo token e contexto:
        declaração var/tipada; atribuição; print; send
        bloco seq/par; if/else; while; do-while; for
        classe; função; return; break; continue
        bloco com chaves; expressão com terminador
    construir o nó dataclass correspondente, preservando localização
    retornar nó; não descartar token desconhecido para prosseguir

PARSE_EXPRESSION(): retornar PARSE_OR()
PARSE_OR(): combinar PARSE_AND enquanto houver ||
PARSE_AND(): combinar PARSE_COMPARISON enquanto houver &&
PARSE_COMPARISON(): combinar PARSE_TERM para == != < > <= >=
PARSE_TERM(): combinar PARSE_FACTOR para + e -
PARSE_FACTOR(): combinar PARSE_UNARY para * / %
PARSE_UNARY():
    se +, - ou !: retornar UnaryExpr(operador, PARSE_UNARY())
    retornar PARSE_PRIMARY()
PARSE_PRIMARY():
    reconhecer literal, identificador, this, new, lista, matriz,
    input, canal, receive, chamada, acesso/índice, fork ou join
    para '(': analisar expressão e exigir ')'
    encadear acessos e chamadas conforme a produção
    se nenhuma produção corresponde: lançar ParseError
```

Os laços constroem operadores binários associativos à esquerda. Comparações
usam um mesmo nível; não se promete a semântica de comparações encadeadas de
Python. Parênteses retornam a expressão interna, sem um nó artificial.

```text
PARSE_FORK(token_fork):
    se local: destino ← TaskDestination(kind = local)
    senão exigir remote '(' expressão_host ',' expressão_porta ')'
    exigir identificador da função e lista de argumentos entre parênteses
    se sufixo contextual 'on':
        exigir 'core' '(' expressão_seletor ')'
        destino.core ← expressão_seletor
    retornar ForkExpr(função, argumentos, destino, localização)

PARSE_JOIN():
    exigir join '(' IDENTIFIER ')'
    retornar JoinExpr(IdentifierExpr(handle), localização)
```

Ver a [BNF](../BNF-grammar.md) para alternativas completas, declarações de
classes, funções e as duas formas de for. As abreviações acima não introduzem
novas produções ou tolerância a erros.
A restrição de afinidade a Fork local é verificada pelo semântico: o parser
pode construir o nó remoto com seletor, mas a análise impede sua compilação.

## 3. Analisador semântico

Fonte: [semantic.py](../src/semantic.py), `SemanticAnalyzer.analyze`,
`_collect_declarations`, `_infer_signatures`, `validate_node`, `_validate_node`,
`_infer_type`, `_check_arguments`, `_endpoint`, `_core_affinity` e `_report`.
Entrada: Program. Saída: bool, diagnostics e símbolos/escopos coletados.

```text
ANALYZE(programa):
    reinicializar analisador, contexto e escopo global
    COLLECT_DECLARATIONS(programa)       # classes, métodos, funções, assinaturas
    INFER_SIGNATURES()                  # inferência disponível na implementação
    ativar coleta do histórico de escopos
    para cada classe: detectar ciclos seguindo a cadeia de superclasses
    para cada comando do programa: VALIDATE_NODE(comando)
    para cada Fork e chamada feita em fronteira independente:
        percorrer grafo de chamadas transitivo, com conjunto de visitados
        reunir capturas de estado global e despachos não resolvidos
        se houver captura indevida ou receptor desconhecido: REPORT(erro)
    retornar NÃO _has_errors

VALIDATE_NODE(nó):
    guardar nó/pai anteriores para contexto e localização
    VALIDATE_NODE_INTERNO(nó)
    restaurar nó/pai anteriores

VALIDATE_NODE_INTERNO(nó):
    declaração: validar tipo, inicialização, compatibilidade e duplicidade
    identificador/atribuição: LOOKUP, validar referência, tipo e escrita
    bloco: entrar em escopo, visitar comandos e sair do escopo
    função/método: definir contexto, parâmetros e validar corpo/retornos
    classe: validar superclasse, membros e métodos no contexto da classe
    this: exigir contexto de classe
    return: exigir contexto de função e retorno compatível
    chamada: resolver função/método/builtin; conferir aridade e tipos
    controle: validar condições, corpos e uso de break/continue em laço
    expressão: validar operandos, operadores, índices e tipos conhecidos
    par: abrir fronteiras de tarefas, impedir escrita indevida no estado externo
    fork: resolver função, validar argumentos, destino e ausência de capturas
    join: exigir símbolo de tarefa inicializada/compatível e recuperar tipo
    canal: validar host, porta, objeto de canal e tipo das mensagens
    afinidade: validar seletor numérico inteiro não negativo quando determinável
```

Uma parte das verificações é necessariamente dinâmica: portas/CPUs recebidas
em runtime, índices, limites de serialização, erros de socket e de tarefas.
`unknown`/`var` participam da inferência quando o tipo não é explicitado. O backend distingue `number` (`double`) de `int` (`std::int64_t`) e aplica verificações próprias para operações inteiras. A análise semântica não pretende constituir uma prova formal de correção de tipos.

## 4. Tabela de símbolos e escopos

Implementação real: dataclass `Symbol`, pilha `_scopes`, dicionários `_classes`,
`_functions`, `_callables`, etiquetas `_scope_tags` e `scope_history` dentro
de SemanticAnalyzer. Não existe uma classe Python SymbolTable independente.

Entrada: nome, tipo, parâmetros e localização; saída: símbolo ou diagnóstico.

```text
ENTER_SCOPE():
    empilhar dicionário vazio em _scopes
    criar etiqueta com id incremental, rótulo do nó/global e id do pai
    empilhar etiqueta em _scope_tags

DEFINE_SYMBOL(nome, tipo, linha, parâmetros):
    se nome já pertence ao último escopo: REPORT(declaração duplicada)
    senão:
        determinar categoria (função, classe, parâmetro ou variável)
        inserir Symbol no último escopo

LOOKUP(nome):
    para escopo do mais interno ao global:
        se nome pertence ao escopo: retornar símbolo
    retornar nenhum

EXIT_SCOPE():
    se não for o escopo global:
        se coleta habilitada e escopo não vazio:
            guardar cópia do dicionário e etiqueta em scope_history
        desempilhar dicionário e etiqueta

MEMBER(classe, nome, métodos):
    seguir classe e superclasses com conjunto de visitados
    consultar tabela de atributos ou métodos
    retornar membro encontrado ou nenhum
```

Os registros Symbol mantêm, conforme a categoria, tipo, parâmetros, retorno,
membros, superclass, definição, capturas e chamadas. `_symbol_rows` em
`educational_pipeline.py` converte essas informações em linhas JSON para a
interface. Histórico de escopos não é armazenamento persistente.

## 5. Tratamento de erros e barreira para o backend

Fontes: [diagnostics.py](../src/diagnostics.py), LexerError, ParseError,
`SemanticAnalyzer._report`, [main.py](../main.py),
[educational_pipeline.py](../src/educational_pipeline.py) e toolchain.

```text
REPORT(linha, mensagem):
    criar Diagnostic(SEMANTICO, mensagem + contexto da função, linha, coluna)
    acrescentar a diagnostics; imprimir em stderr; _has_errors ← verdadeiro

COMPILE_FILE(caminho, saída, tac_only):
    ler UTF-8; se arquivo ausente: diagnosticar e retornar falso
    tentar Lexer.tokenize; se LexerError: apresentar e retornar falso
    tentar Parser.parse; se CompilerError: apresentar e retornar falso
    se NÃO SemanticAnalyzer.analyze: apresentar falha e retornar falso
    gerar TAC a partir da AST
    se tac_only: retornar verdadeiro
    tentar CppCodeGenerator.generate(AST, saída)
    se CompilerError: apresentar e retornar falso

ANALYZE_SOURCE(código, etapa):
    iniciar fases como 'não executada'
    executar cada fase somente até a etapa solicitada
    devolver tokens, AST, símbolos, TAC ou C++, quando produzidos
    se semântico retorna falso: devolver diagnósticos e não gerar TAC/C++
    se CompilerError: marcar a fase reprovada e devolver Diagnostic em JSON
```

`CppCodeGenerator.generate` escreve C++, chama `toolchain.compile_cpp` e
verifica retorno do subprocesso. Toolchain seleciona `MINIPAR_CXX`/`CXX`,
prepara PATH de DLLs e usa C++20, `-O3`, `-pthread` e Winsock no Windows.
Erros/timeout de G++ e códigos de saída nativos são expostos pelas interfaces.
No runtime C++, exceções de tarefas chegam ao Join; não se convertem em
resultados fictícios. Erros léxicos/sintáticos interrompem a fase; erros
semânticos podem ser acumulados. Localização é preservada quando disponível,
com fallback 1 para estruturas sem posição mais precisa.
