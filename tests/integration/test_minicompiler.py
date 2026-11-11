"""Todos os resultados sao produzidos pelo MiniPar compilado, inclusive o ARM."""
from pathlib import Path
import re
import subprocess
import sys
import pytest
from tools import validate_programs as pipeline
from tools.validate_minicompiler import SOURCE, MANDATORY, section, check_success
from tools.arm_validation import validate_arm

pytestmark = pytest.mark.native


@pytest.fixture(scope='module')
def compiler(tmp_path_factory):
    record = pipeline.build(SOURCE, tmp_path_factory.mktemp('minicompiler'))
    assert record['phases']['native_compilation'] == pipeline.PASS, record
    return record


def execute(compiler, expression, path):
    return pipeline.run(compiler, expression + '\n', env={'MINIPAR_ARM_OUTPUT': str(path)})


VALID = MANDATORY + [
    ('2+3*4', 14), ('(2+3)*4', 20), ('20-3-2', 15), ('48/4/3', 4),
    ('-(2+3)*4', -20), ('--7 + +3', 10), ('-12/3', -4), ('12/-3', -4),
    ('-12/-3', 4), ('0/-7', 0), ('81/(3*3)', 9), ('2.0+3', 5),
    ('1000000+234567', 1234567), ('2147483647', 2147483647),
    ('-2147483648', -2147483648), ('(-2147483648)/2', -1073741824),
    ('(-2147483648)/(-2147483648)', 1), ('32767*65536', 2147418112),
]


@pytest.mark.parametrize(('expression', 'expected'), VALID)
def test_native_expression_and_actual_arm_execution(compiler, tmp_path, expression, expected):
    path = tmp_path / 'result.arm'
    result = execute(compiler, expression, path)
    check_success(result, path, expected)
    verified = validate_arm(path, tmp_path / 'result.elf')
    assert verified['assembler']['returncode'] == 0, verified
    assert verified['emulation']['r0_signed'] == expected, verified
    assert verified['emulation']['r0_unsigned'] == expected & 0xffffffff
    assert verified['emulation']['stack_balanced'] and verified['emulation']['aligned']


def test_tokens_ast_symbols_and_tac_are_structural(compiler, tmp_path):
    result = execute(compiler, MANDATORY[0][0], tmp_path / 'first.arm')
    data = check_success(result, tmp_path / 'first.arm', 22)
    kinds = {'(': 'LPAREN', ')': 'RPAREN', '+': 'ADD', '-': 'SUB', '*': 'MUL'}
    assert data['TOKENS'].splitlines() == [
        f'TOKEN {kinds.get(char, "NUMBER")} {char} 1 {i}' for i, char in enumerate(MANDATORY[0][0], 1)]
    assert data['AST'].splitlines() == ['ROOT BINARY -', '  L BINARY *', '    L BINARY +',
        '      L NUMBER 2', '      R NUMBER 4', '    R NUMBER 7', '  R BINARY *',
        '    L NUMBER 5', '    R NUMBER 4']
    assert data['SIMBOLOS'].splitlines() == [f'SIMBOLO {n} CONST {n}' for n in (2, 4, 7, 5)]
    assert data['TAC'] == 't1 = 2 + 4\nt2 = t1 * 7\nt3 = 5 * 4\nt4 = t2 - t3'
    other = execute(compiler, MANDATORY[1][0], tmp_path / 'second.arm')
    assert section(other.stdout, 'TAC') == 't1 = 8 * 7\nt2 = 10 - t1\nt3 = t2 + 4\nt4 = t3 * 2'


@pytest.mark.parametrize(('expression', 'phase'), [
    ('', 'LEXICO'), ('  ', 'LEXICO'), ('2@3', 'LEXICO'), ('1..2', 'LEXICO'),
    ('1.', 'LEXICO'), ('.5', 'LEXICO'), ('2+', 'SINTATICO'), ('*2', 'SINTATICO'),
    ('()', 'SINTATICO'), ('(2+3', 'SINTATICO'), ('2+3)', 'SINTATICO'),
    ('2 3', 'SINTATICO'), ('2(3)', 'SINTATICO'), ('1e2', 'SINTATICO'),
    ('missing+1', 'SEMANTICO'), ('3/(2-2)', 'AVALIACAO'),
    ('(' * 129 + '1' + ')' * 129, 'SINTATICO'), ('-' * 129 + '1', 'SINTATICO'),
    ('+'.join(['1'] * 130), 'SINTATICO'), ('9' * 400, 'LEXICO'),
    ('1' * 4097, 'LEXICO'), ('+'.join(['1'] * 513), 'LEXICO'),
])
def test_invalid_input_is_diagnosed_without_assembly(compiler, tmp_path, expression, phase):
    path = tmp_path / 'invalid.arm'
    result = execute(compiler, expression, path)
    assert result.returncode == 1 and result.stderr == '', result
    assert re.search(rf'ERRO {phase} [1-9]\d* [1-9]\d* ', result.stdout)
    assert 'STATUS APROVADO' not in result.stdout and 'RESULTADO ' not in result.stdout
    assert not path.exists()


@pytest.mark.parametrize('expression', ['5/2', '1.5+0.5', '2147483648', '2147483647+1',
    '-2147483648/-1', '50000*50000', '-(-2147483648)'])
def test_arm_rejects_fractional_intermediates_and_signed_overflow(compiler, tmp_path, expression):
    path = tmp_path / 'unsupported.arm'
    result = execute(compiler, expression, path)
    assert result.returncode == 2 and result.stderr == ''
    assert 'RESULTADO ' in result.stdout and 'ERRO ARM ' in result.stdout
    assert 'STATUS ARM_NAO_SUPORTADO' in result.stdout and not path.exists()


@pytest.mark.parametrize('shape', ['deep', 'wide'])
def test_register_reuse_stack_and_literal_pool_ranges(compiler, tmp_path, shape):
    if shape == 'deep':
        expression = '1'
        for _ in range(60): expression = '1+(' + expression + ')'
        expected = 61
    else:
        level = ['1000000'] * 256
        while len(level) > 1: level = [f'({a}+{b})' for a, b in zip(level[::2], level[1::2])]
        expression = level[0]; expected = 256000000
    path = tmp_path / 'large.arm'
    result = execute(compiler, expression, path)
    check_success(result, path, expected)
    report = validate_arm(path, tmp_path / 'large.elf')
    assert report['assembler']['returncode'] == 0, report
    assert report['emulation']['r0_signed'] == expected
    if shape == 'deep': assert report['emulation']['max_stack_bytes'] >= 480
    else: assert '__expr_pool_' in path.read_text()


@pytest.fixture(scope='module')
def api_driver(tmp_path_factory):
    main = '''var compiler = new MiniCompiler();
        require(compiler.symbols.define("x",9),"define x");
        require(compiler.symbols.define("t1",5),"define t1");
        for(var i in range(2)) {
            var source=input(); var path=input();
            if(source=="multiline") { source="1+\\n @"; }
            var success=compiler.compile(source,path);
        }'''
    record = pipeline.build(SOURCE, tmp_path_factory.mktemp('minicompiler-api'), main=main)
    assert record['phases']['native_compilation'] == pipeline.PASS, record
    return record


def test_defined_variables_and_compilation_reset(api_driver, tmp_path):
    paths = [tmp_path / 'var.arm', tmp_path / 'next.arm']
    result = pipeline.run(api_driver, f'x+t1*2\n{paths[0]}\n4+5\n{paths[1]}\n')
    assert result.returncode == 0 and result.stderr == ''
    outputs = result.stdout.split('STATUS APROVADO')
    assert section(outputs[0], 'TAC') == 't2 = t1 * 2\nt3 = x + t2'
    assert 'SIMBOLO x VAR 9' in outputs[0] and 'SIMBOLO t1 VAR 5' in outputs[0]
    assert section(outputs[1], 'TAC') == 't2 = 4 + 5'
    assert 'SIMBOLO 2 CONST' not in outputs[1]
    for path, expected in zip(paths, (19, 9)):
        report = validate_arm(path, path.with_suffix('.elf'))
        assert report['assembler']['returncode'] == 0, report
        assert report['emulation']['r0_signed'] == expected


def test_error_location_and_recovery_in_same_compiler(api_driver, tmp_path):
    bad, good = tmp_path / 'bad.arm', tmp_path / 'good.arm'
    result = pipeline.run(api_driver, f'multiline\n{bad}\n6*7\n{good}\n')
    assert result.returncode == 0
    assert 'ERRO LEXICO 2 2 ' in result.stdout and 'RESULTADO 42' in result.stdout
    assert not bad.exists() and good.exists()


@pytest.mark.parametrize('name', ['wrong.txt', 'missing/file.arm'])
def test_file_errors_are_reported(compiler, tmp_path, name):
    path = tmp_path / name
    result = execute(compiler, '1+2', path)
    assert result.returncode == 1 and 'ERRO IO 1 1 ' in result.stdout and result.stderr == ''
    assert not path.exists()


@pytest.mark.parametrize('expression,success', [('((10-8*7)+4)*2', True), ('1/0', False)])
def test_existing_web_executes_minicompiler_and_downloads_arm(monkeypatch, expression, success):
    import app as web
    monkeypatch.chdir(pipeline.ROOT)
    path = pipeline.ROOT / 'output/pytest-web-11.arm'
    monkeypatch.setenv('MINIPAR_ARM_OUTPUT', str(path))
    client = web.app.test_client()
    assert SOURCE.name in client.get('/api/tests').get_json()['tests']
    source = client.post('/api/get_test', json={'filename': SOURCE.name}).get_json()['code']
    assert source == SOURCE.read_text(encoding='utf-8')
    result = client.post('/api/compile', json={'filename': 'pytest_web_11.minipar',
        'code': source, 'inputs': [expression]}).get_json()
    assert result['success'] is success, result
    assert result['cpp'] and result['tac']
    if success:
        assert 'RESULTADO -84' in result['stdout'] and len(result['artifacts']) == 1
        download = client.get(result['artifacts'][0]['url'])
        assert download.status_code == 200 and download.mimetype == 'text/plain'
        assert 'attachment;' in download.headers['Content-Disposition']
        assert download.data == path.read_bytes()
    else: assert result['artifacts'] == []
    assert client.get('/api/artifacts/../../referencias/Codigo-Assembly-ARMV7.arm.txt').status_code == 404


def test_terminal_interface_executes_real_binary_with_stdin(tmp_path):
    # Um processo filho herda stdin real; nenhuma simulacao de subprocess.run/input.
    arm = tmp_path / 'terminal.arm'
    script = '''import menu, main
assert any(p.endswith("teste11_minicompilador_armv7.minipar") for p in menu.obter_testes())
assert main.compile_file("tests/teste11_minicompilador_armv7.minipar", "pytest_terminal_11")
menu.executar_binario("pytest_terminal_11", interactive=True)
'''
    result = subprocess.run([sys.executable, '-c', script], input='((2+4)*7)-(5*4)\n',
        capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120,
        cwd=pipeline.ROOT, env={**pipeline.runtime_environment(), 'MINIPAR_ARM_OUTPUT': str(arm)})
    assert result.returncode == 0, result.stderr
    assert 'RESULTADO 22' in result.stdout and 'STATUS APROVADO' in result.stdout
    assert arm.is_file()
