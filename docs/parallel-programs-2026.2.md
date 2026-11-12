# Programas paralelos — Testes 8, 9 e 10

Os três programas em `tests/` demonstram o uso de Fork/Join, comunicação por canais e execução de tarefas nativas. Cada um avalia **160 atividades** (40 alunos × 4 atividades), comparando processamento sequencial e paralelo.

| Teste | Arquivo | Tarefas paralelas | Conteúdo adicional |
| --- | --- | ---: | --- |
| 8 | `tests/teste8_avaliacao_paralela.minipar` | 4 | Quatro avaliadores: Professor e três Monitores |
| 9 | `tests/teste9_avaliacao_mandelbrot.minipar` | 5 | Mandelbrot em ASCII (50 × 20) |
| 10 | `tests/teste10_avaliacao_fractais.minipar` | 6 | Mandelbrot ASCII e tapete de Sierpinski SVG |

## Avaliação e sincronização

A modalidade sequencial processa os registros em uma sequência de chamadas. Na modalidade paralela, o conjunto é repartido entre quatro avaliadores; cada tarefa recebe seus dados de entrada e devolve os resultados sem compartilhar variáveis mutáveis com as demais.

As tarefas anunciam sua disponibilidade por `c_channel` antes da liberação da barreira. Os resultados são recolhidos com `join`. Os validadores verificam a totalidade das 160 atividades e a inexistência de perdas ou duplicações.

## Fractais

O Teste 9 gera a representação ASCII do conjunto de Mandelbrot. O Teste 10 mantém essa saída e produz também o tapete de Sierpinski, profundidade 4, em SVG. Os dois modos de execução produzem artefatos comparáveis.

Os arquivos de saída são criados na pasta `output/`. Exemplos de evidências versionadas estão em [evidencias/fractais](evidencias/fractais/), incluindo os SVG e textos exportados.

## Compilar e executar

```powershell
py main.py tests/teste8_avaliacao_paralela.minipar
py main.py tests/teste9_avaliacao_mandelbrot.minipar
py main.py tests/teste10_avaliacao_fractais.minipar
$env:Path = 'C:\msys64\mingw64\bin;' + $env:Path
.\output\teste8_avaliacao_paralela.exe
.\output\teste9_avaliacao_mandelbrot.exe
.\output\teste10_avaliacao_fractais.exe
```

Validação conjunta:

```powershell
py tools/validate_parallel.py
```

## Desempenho observado

Os valores abaixo correspondem às execuções reproduzidas no relatório técnico e são medições pontuais, não garantias de aceleração.

| Teste | Sequencial (s) | Paralelo (s) | Speedup |
| --- | ---: | ---: | ---: |
| 8 | 0,0222 | 0,0195 | 1,143 |
| 9 | 0,0221 | 0,0453 | 0,488 |
| 10 | 0,0277 | 0,5576 | 0,050 |

O Teste 8 apresentou pequeno ganho nessa execução, enquanto os testes 9 e 10 apresentaram desaceleração, devido aos custos de inicialização, sincronização e transporte de mensagens em relação ao volume de trabalho medido. Variações do sistema e da máquina podem modificar esses tempos.

Ver também: [afinidade de CPU](affinity-distributed-2026.2.md) e [testes de integração](testes-integracao-2026.2.md).
