"""Linha de base por fase; conserva falhas e nunca aprova binário não executado."""
from pathlib import Path
import contextlib
import hashlib
import io
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
import argparse

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'src')]
from lexer import Lexer
from parser import Parser
from semantic import SemanticAnalyzer
from tac import TACGenerator
from codegen import CppCodeGenerator
from toolchain import compile_cpp, compiler_path, executable_suffix, runtime_environment


def run_case(source_path):
    source = source_path.read_text(encoding='utf-8')
    directory = ROOT / 'output' / 'baseline' / source_path.stem
    directory.mkdir(parents=True, exist_ok=True)
    result = {'file': str(source_path.relative_to(ROOT)), 'sha256': hashlib.sha256(source_path.read_bytes()).hexdigest(),
              'phases': {}, 'execution_validated': False}
    phases = result['phases']
    log = io.StringIO()
    phase = 'lexical'
    try:
        with contextlib.redirect_stderr(log):
            tokens = Lexer(source).tokenize()
            phases[phase] = {'status': 'ok', 'token_count': len(tokens)}
            phase = 'syntactic'
            ast = Parser(tokens).parse()
            phases[phase] = {'status': 'ok'}
            phase = 'semantic'
            if not SemanticAnalyzer().analyze(ast):
                phases[phase] = {'status': 'failed', 'stderr': log.getvalue()}
                return result
            phases[phase] = {'status': 'ok'}
            phase = 'tac'
            tac = TACGenerator().generate_text(ast)
            (directory / 'program.tac').write_text(tac, encoding='utf-8')
            phases[phase] = {'status': 'ok', 'note': 'Emissao apenas; nao valida semantica do TAC.'}
            phase = 'cpp_generation'
            cpp = CppCodeGenerator().render(ast)
            cpp_path = directory / 'program.cpp'
            cpp_path.write_text(cpp, encoding='utf-8')
            phases[phase] = {'status': 'ok'}
            phase = 'native_compilation'
            executable = directory / ('program' + executable_suffix())
            built = compile_cpp(cpp_path, executable)
            phases[phase] = {'status': 'ok' if built.returncode == 0 else 'failed',
                             'command': built.args, 'returncode': built.returncode,
                             'stdout': built.stdout, 'stderr': built.stderr}
            if built.returncode != 0:
                return result
            phase = 'execution'
            inputs = {
                'teste11_minicompilador_armv7': '((2+4)*7)-(5*4)\n',
                'teste1_calculadora_cliente_servidor': '+\n2\n3\n',
                'teste5_recomendacao': '1\n0\n0\n0\n0\n1\n0\n0\n0\n1\n0\n0\n1\n0\n0\n0\n',
                'teste6_quicksort_classes': '10 -3 -40 80 70 -100\n',
            }.get(source_path.stem, '')
            ran = subprocess.run([str(executable)], input=inputs, capture_output=True,
                                 text=True, encoding='utf-8', errors='replace', timeout=15,
                                 env=runtime_environment())
            phases[phase] = {'status': 'ok' if ran.returncode == 0 else 'failed', 'command': ran.args,
                             'stdin': inputs, 'returncode': ran.returncode, 'stdout': ran.stdout, 'stderr': ran.stderr}
            if source_path.stem == 'smoke':
                result['execution_validated'] = ran.returncode == 0 and ran.stdout == '42\n'
            else:
                result['validation_note'] = 'Saida e retorno registrados; nao equivale a aprovacao funcional do exemplo.'
    except (Exception, SystemExit) as exc:
        phases[phase] = {'status': 'failed', 'error': repr(exc), 'stderr': log.getvalue()}
    return result


def main():
    # Relatórios diferentes dos arquivos da auditoria original.
    arguments = argparse.ArgumentParser(description=__doc__)
    arguments.add_argument('--report', default='output/validacoes/baseline-funcional.json')
    output = ROOT / arguments.parse_args().report
    report = {'timestamp_utc': datetime.now(timezone.utc).isoformat(), 'python': sys.version,
              'platform': platform.platform(), 'compiler': compiler_path(), 'cases': []}
    version = subprocess.run([compiler_path(), '--version'], capture_output=True, text=True,
                             env=runtime_environment(), timeout=10)
    report['compiler_version'] = version.stdout
    for path in [ROOT / 'tests/fixtures/smoke.minipar', *sorted((ROOT / 'tests').glob('*.minipar'))]:
        result = run_case(path)
        report['cases'].append(result)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
        print(path.name, {key: value['status'] for key, value in result['phases'].items()}, flush=True)
    print('Relatorio:', output)
    # Retorno não zero se qualquer exemplo falha: não ocultar falhas complexas.
    return 0 if all(c['phases'].get('execution', {}).get('status') == 'ok' for c in report['cases']) else 1


if __name__ == '__main__':
    sys.exit(main())
