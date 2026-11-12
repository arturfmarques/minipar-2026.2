# Integração das interfaces Web — MiniPar 2026.2

O projeto disponibiliza duas páginas no **mesmo servidor Flask**: a IDE Web original em `/` e a interface educacional em `/educacional`. Ambas utilizam o compilador MiniPar existente e compartilham um cabeçalho de navegação.

## Arquitetura

- `app.py` concentra a aplicação principal e registra as rotas da interface educacional.
- `educational_web.py` disponibiliza as operações específicas de análise por etapa.
- `src/educational_pipeline.py` usa os analisadores e geradores do compilador.
- `templates/_web_header.html` oferece a navegação entre as duas páginas.
- `static/js/web-common.js` e `static/css/web-common.css` implementam comportamentos e estilos compartilhados.

A passagem entre as páginas preserva o texto do editor na mesma aba por meio de `sessionStorage`. Isso transfere a fonte, mas não transforma resultados antigos em resultados da nova análise: ao editar o código, as fases precisam ser executadas novamente.

## IDE original

A IDE mantém seleção de programas, edição de código, compilação e execução, com apresentação do C++ gerado, TAC e saída do processo. O fluxo chama o mesmo compilador utilizado pelo terminal.

## Interface educacional

A nova interface separa Tokens, AST gráfica, Semântica, símbolos, TAC e C++. O usuário pode consultar detalhes, copiar conteúdo gerado, executar programas com entrada e baixar artefatos.

A AST visualizada corresponde aos nós reais serializados pelo serviço de análise. Os filtros de tokens e as interações de zoom, expansão e seleção operam sobre essa estrutura, sem substituir o parser por dados de demonstração.

## Como executar

```powershell
py -m pip install -r requirements.txt
py app.py
```

Acesse `http://127.0.0.1:5000/` ou `http://127.0.0.1:5000/educacional`.

## Validação

Os testes das interfaces abrangem rotas Flask, análises por etapa, execução de programas, transferência de código e comportamento dos componentes interativos.

```powershell
py -m pytest tests/integration/test_web.py tests/integration/test_educational_web.py tests/integration/test_web_unified.py
```

Consulte [web-educacional-2026.2.md](web-educacional-2026.2.md) para a descrição detalhada da interface educacional.
