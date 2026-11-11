"""Executa o minicompilador MiniPar e valida seu ARM com assembler e emulador."""
import argparse
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools import validate_programs as pipeline
from tools.arm_validation import validate_arm

SOURCE = pipeline.ROOT / 'tests/teste11_minicompilador_armv7.minipar'
MANDATORY = [('((2+4)*7)-(5*4)', 22), ('((10-8*7)+4)*2', -84), ('((2+4)*7)-(5*4)', 22)]


def section(stdout, name):
    return stdout.split(name + '_BEGIN\n', 1)[1].split(name + '_END', 1)[0].strip('\n')


def check_success(result, path, expected):
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stderr == '', result.stderr
    assert 'STATUS APROVADO' in result.stdout
    value = float(re.search(r'^RESULTADO (.+)$', result.stdout, re.M)[1])
    assert value == expected, (value, expected)
    assembly = path.read_text(encoding='utf-8')
    assert section(result.stdout, 'ARM') == assembly.rstrip('\n')
    assert '.arch armv7-a\n.arm\n' in assembly and '__expr_done:' in assembly
    return {name: section(result.stdout, name) for name in ('TOKENS', 'AST', 'SIMBOLOS', 'TAC')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', default='output/validacoes/teste11/validacao.json')
    args = parser.parse_args()
    report_path = pipeline.ROOT / args.report
    evidence = report_path.parent
    evidence.mkdir(parents=True, exist_ok=True)
    built = pipeline.build(SOURCE, pipeline.ROOT / 'output/validation-11')
    report = {'build': built, 'cases': [], 'cpulator': {'status': 'NAO VERIFICADA',
              'reason': 'Este validador cobre Zig/LLVM e Unicorn; CPUlator exige verificacao separada no navegador.'}}
    pipeline.save(report_path, report)
    assert built['phases']['native_compilation'] == pipeline.PASS, built
    cases = MANDATORY + [('2+3*4', 14), ('-(2+3)*4', -20), ('1000000+234567', 1234567),
                        ('(-2147483648)/2', -1073741824), ('81/(3*3)', 9)]
    for index, (expression, expected) in enumerate(cases, 1):
        arm = evidence / f'expressao-{index}.arm'
        result = pipeline.run(built, expression + '\n', env={'MINIPAR_ARM_OUTPUT': str(arm)})
        record = {'expression': expression, 'expected': expected, 'execution': dict(built['execution'])}
        report['cases'].append(record)
        pipeline.save(report_path, report)
        record['sections'] = check_success(result, arm, expected)
        (evidence / f'expressao-{index}.txt').write_text(result.stdout, encoding='utf-8')
        record['arm'] = validate_arm(arm, pipeline.ROOT / f'output/validation-11/expression-{index}.elf')
        pipeline.save(report_path, report)
        assert record['arm']['assembler']['returncode'] == 0, record
        assert record['arm']['emulation']['r0_signed'] == expected, record
        record['status'] = 'APROVADO'
        pipeline.save(report_path, report)
        print(f'{index}: {expression} = {expected}; ARM r0={record["arm"]["emulation"]["r0_unsigned"]:#010x}', flush=True)
    built['phases']['results'] = pipeline.PASS
    pipeline.save(report_path, report)
    return 0


if __name__ == '__main__':
    sys.exit(main())
