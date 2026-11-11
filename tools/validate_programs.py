"""Pipeline real e oraculos de resultados dos programas obrigatorios 1 a 7.

Os oraculos apenas verificam stdout do executavel; nunca substituem MiniPar.
"""
from __future__ import annotations
import argparse
import ast as literal_ast
import contextlib
import hashlib
import io
import json
import math
from pathlib import Path
import re
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from ast_nodes import ClassDecl, FuncDecl, Program, walk
from lexer import Lexer
from parser import Parser
from semantic import SemanticAnalyzer
from tac import TACGenerator
from codegen import CppCodeGenerator
from toolchain import compiler_path, compile_command, executable_suffix, runtime_environment

PASS, FAIL, NOT_RUN = 'APROVADO', 'REPROVADO', 'NÃO EXECUTADO'
PHASES = ('lexical', 'parser', 'semantic', 'tac', 'cpp_generation', 'native_compilation', 'execution', 'results')
SOURCES = {i: next((ROOT / 'tests').glob(f'teste{i}_*.minipar')) for i in range(1, 8)}
HISTORY = [1, 0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 1, 0, 0, 0]
CATALOG = ['Smartphone', 'Laptop', 'Tablet', 'Fones de ouvido', 'Camisa', 'Jeans', 'Jaqueta', 'Sapatos',
           'Geladeira', 'Micro-ondas', 'Máquina de lavar', 'Ar condicionado', 'Ficção', 'Não-ficção', 'Ficção científica', 'Fantasia']


def save(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def tac_contract(program, text):
    """Propriedades estruturais verificaveis; nao e um interpretador TAC."""
    labels = set(re.findall(r'^(\w+):$', text, re.M))
    targets = set(re.findall(r'\bgoto (\w+)', text))
    assert targets <= labels, f'Rotulos ausentes: {targets - labels}'
    definitions = set(re.findall(r'^(t\d+) =', text, re.M))
    used = set(re.findall(r'\bt\d+\b', text))
    assert used <= definitions, f'Temporarios sem definicao: {used - definitions}'
    for node in program.statements:
        if isinstance(node, FuncDecl): assert f'func {node.name}:' in text
        if isinstance(node, ClassDecl):
            for method in node.methods: assert f'func {node.name}.{method.name}:' in text
    assert text == TACGenerator().generate_text(program), 'TAC nao deterministico'
    return {'labels': len(labels), 'temporaries': len(definitions), 'jumps': len(targets),
            'calls': len(re.findall(r'call(?:method)? ', text)), 'executor_tac': False}


def build(source_path, directory, main=None, checked=True):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    record = {'file': str(source_path.relative_to(ROOT)), 'source_sha256': hashlib.sha256(source_path.read_bytes()).hexdigest(),
              'main_override': main, 'checked_vectors': checked, 'phases': {p: NOT_RUN for p in PHASES}}
    phase = 'lexical'
    try:
        source = source_path.read_text(encoding='utf-8')
        tokens = Lexer(source).tokenize()
        record['phases'][phase] = PASS
        phase = 'parser'
        program = Parser(tokens).parse()
        if main is not None:
            driver = Parser(Lexer(main).tokenize()).parse()
            program = Program([s for s in program.statements if isinstance(s, (FuncDecl, ClassDecl))] + driver.statements)
        record['phases'][phase] = PASS
        phase = 'semantic'
        analyzer = SemanticAnalyzer()
        with contextlib.redirect_stderr(io.StringIO()):
            valid = analyzer.analyze(program)
        assert valid, '\n'.join(map(str, analyzer.diagnostics))
        record['phases'][phase] = PASS
        phase = 'tac'
        text = TACGenerator().generate_text(program)
        record['tac_checks'] = tac_contract(program, text)
        (directory / 'program.tac').write_text(text, encoding='utf-8')
        record['phases'][phase] = PASS
        phase = 'cpp_generation'
        cpp = directory / 'program.cpp'
        cpp.write_text(CppCodeGenerator(analyzer).render(program), encoding='utf-8')
        record['phases'][phase] = PASS
        phase = 'native_compilation'
        executable = directory / ('program' + executable_suffix())
        command = compile_command(cpp, executable, compiler_path())
        if checked: command += ['-D_GLIBCXX_ASSERTIONS']
        compiled = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace',
                                  timeout=120, env=runtime_environment())
        record['compilation'] = {'command': command, 'returncode': compiled.returncode, 'stderr': compiled.stderr}
        assert compiled.returncode == 0, compiled.stderr
        record['phases'][phase] = PASS
        record['executable'] = str(executable)
    except Exception as error:
        record['phases'][phase] = FAIL
        record['error'] = str(error)
    return record


def run(record, stdin='', env=None, timeout=20):
    command = [record['executable']]
    result = subprocess.run(command, input=stdin, capture_output=True, text=True, encoding='utf-8', errors='replace',
                            timeout=timeout, env={**runtime_environment(), **(env or {})})
    record['execution'] = {'command': command, 'stdin': stdin, 'returncode': result.returncode,
                           'stdout': result.stdout, 'stderr': result.stderr}
    record['phases']['execution'] = PASS if result.returncode == 0 else FAIL
    return result


def vector_after(stdout, label):
    line = next(line for line in stdout.splitlines() if line.startswith(label))
    return literal_ast.literal_eval(line[len(label):].strip())


def neuron_oracle(entrada=1, desejado=0, peso=0.5, peso_bias=0.5, taxa=0.01):
    # Transcricao matematica da regra oficial, usada somente como comparador.
    for iteration in range(1, 10001):
        output = int(entrada * peso + peso_bias >= 0)
        error = desejado - output
        if error == 0: return iteration, peso, peso_bias
        peso += taxa * entrada * error
        peso_bias += taxa * error
    raise AssertionError('Oraculo de neuronio nao convergiu')


def validate(number, stdout, history=HISTORY):
    if number == 1:
        assert math.isclose(float(re.search(r'Resultado:\s*([^\n]+)', stdout)[1]), 5)
    elif number == 2:
        assert 'Fatorial de 5: 120' in stdout
        sequence = [int(s) for s in stdout.splitlines() if re.fullmatch(r'\d+', s)]
        assert sequence == [0, 1, 1, 2, 3, 5, 8, 13], sequence
    elif number == 3:
        iteration, weight, bias_weight = neuron_oracle()
        assert int(re.search(r'Iteracoes totais:\s*(\d+)', stdout)[1]) == iteration
        assert math.isclose(float(re.search(r'Peso final:\s*([^\n]+)', stdout)[1]), weight, abs_tol=1e-9)
        assert math.isclose(float(re.search(r'Peso bias final:\s*([^\n]+)', stdout)[1]), bias_weight, abs_tol=1e-9)
        assert re.findall(r'Erro:\s*([^\n]+)', stdout)[-1] == '0'
    elif number == 4:
        predictions = re.findall(r'Input: \[(\d), (\d)\], Predicted Output:\s*([^\n]+)', stdout)
        assert len(predictions) == 4
        assert {(int(a), int(b)) for a, b, _ in predictions} == {(0, 0), (0, 1), (1, 0), (1, 1)}
        for a, b, value in predictions:
            value = float(value)
            assert math.isfinite(value) and 0 <= value <= 1
            assert abs(value - (int(a) ^ int(b))) < 0.1, predictions
    elif number == 5:
        encoded = vector_after(stdout, 'Historico codificado:')
        assert encoded == history
        probabilities = vector_after(stdout, 'Probabilidades:')
        hidden = max(0, sum(history) * 0.5 + 0.5)
        expected = 1 / (1 + math.exp(-(10 * hidden * 0.5 + 0.5)))
        assert len(probabilities) == 16
        assert all(math.isclose(p, expected, abs_tol=5e-6) for p in probabilities)
        names = stdout.split('Produtos recomendados para você:\n', 1)[1].splitlines()
        assert names == [name for name, bought in zip(CATALOG, history) if not bought and expected > 0.5], names
    elif number == 6:
        assert vector_after(stdout, 'Vetor original:') == [10, -3, -40, 80, 70, -100]
        assert vector_after(stdout, 'Vetor ordenado:') == [-100, -40, -3, 10, 70, 80]
    elif number == 7:
        assert vector_after(stdout, 'Array ordenado:') == [5, 12, 33, 61, 98]
    else:
        raise ValueError(number)


def inputs(number):
    return {1: '+\n2\n3\n', 5: '\n'.join(map(str, HISTORY)) + '\n',
            6: '10 -3 -40 80 70 -100\n'}.get(number, '')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, default=Path('output/validacoes/validacao-1a7.json'))
    parser.add_argument('--output', type=Path, default=Path('output/validation-1a7'))
    arguments = parser.parse_args()
    report = {'timestamp_utc': datetime.now(timezone.utc).isoformat(), 'cases': []}
    for number, source in SOURCES.items():
        record = build(source, (ROOT / arguments.output).resolve() / f'teste{number}')
        record['test'] = number
        if record['phases']['native_compilation'] == PASS:
            try:
                executed = run(record, inputs(number))
                assert executed.returncode == 0, executed.stderr
                validate(number, executed.stdout)
                record['phases']['results'] = PASS
            except Exception as error:
                failed_phase = 'results' if record['phases']['execution'] == PASS else 'execution'
                record['phases'][failed_phase] = FAIL
                record['error'] = str(error)
        record['final'] = PASS if all(p == PASS for p in record['phases'].values()) else FAIL
        report['cases'].append(record)
        save(ROOT / arguments.report, report)
        print(f'Teste {number}: {record["final"]}', record.get('error', ''), flush=True)
    return int(any(c['final'] != PASS for c in report['cases']))


if __name__ == '__main__':
    sys.exit(main())
