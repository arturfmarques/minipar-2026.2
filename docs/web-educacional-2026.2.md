# Interface Web educacional — MiniPar 2026.2

A interface educacional é acessada em `http://127.0.0.1:5000/educacional`. Ela utiliza as mesmas etapas e os mesmos geradores do compilador apresentado pelo terminal e pela IDE Web original (`/`).

## Inicialização

```powershell
py -m pip install -r requirements.txt
py app.py
```

O servidor Flask disponibiliza a IDE original em `http://127.0.0.1:5000/` e a interface educacional em `/educacional`.

## Etapas disponíveis

| Área | Conteúdo mostrado |
| --- | --- |
| Tokens | Tipo, lexema, posição, número e filtro de categoria |
| AST | Estrutura gráfica interativa dos nós reais, expansão e detalhes |
| Semântica | Diagnósticos com fase, linha e coluna |
| Tabela de símbolos | Identificadores, categorias, tipos e escopos visitados |
| TAC | Instruções intermediárias geradas a partir da AST |
| C++ | Código C++20 produzido pelo backend principal |
| Compilar e executar | Artefatos nativos, entrada padrão, saída e downloads |

As etapas não usam representações preenchidas manualmente: `src/educational_pipeline.py` chama `Lexer`, `Parser`, `SemanticAnalyzer`, `TACGenerator` e `CppCodeGenerator` existentes.

## AST interativa

A serialização mantém informações dos nós reais da AST, suas relações e detalhes relevantes. A visualização SVG permite expandir e recolher subárvores, aplicar zoom, mover a área de visualização e consultar informações de cada nó. Em árvores extensas, a exploração por subárvores evita sobrecarregar a tela.

## Integração e arquivos

- `educational_web.py`: rotas Flask e execução de trabalhos.
- `src/educational_pipeline.py`: serviços de análise por etapa.
- `templates/educacional.html`: layout, editor e painéis.
- `static/js/educacional.js` e `static/js/educacional-view.js`: interação e visualização.
- `static/css/educacional.css`: estilos da interface.

A compilação gera arquivos em `output/educacional/`, que não são enviados ao repositório por serem artefatos temporários. Ao alternar para a IDE original na mesma aba, o editor pode preservar o código-fonte por meio do navegador; resultados anteriores exigem nova análise ou compilação.

## Testes

```powershell
py -m pytest tests/integration/test_educational_web.py tests/integration/test_web_unified.py
```

Mais detalhes sobre a navegação compartilhada estão em [web-integrada-2026.2.md](web-integrada-2026.2.md).
