from pathlib import Path
import subprocess
import sys
import pytest
from codegen import CppCodeGenerator
from semantic import SemanticAnalyzer
from toolchain import compile_cpp, compiler_path, executable_suffix, runtime_environment, ToolchainError

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.native
@pytest.mark.parametrize(('source', 'stdin', 'expected'), [
    ('seq { print(42); }', '', '42\n'),
    ('seq { print(2 + 3 * 4); }', '', '14\n'),
    ('var sum = 0; for (var i = 0; i < 5; i = i + 1) { sum = sum + i; } print(sum);', '', '10\n'),
    ('var n = to_number(input()); print(n * 2);', '21\n', '42\n'),
    ('func double_value(x) { return x * 2; } print(double_value(21));', '', '42\n'),
])
def test_real_native_pipeline(parse, tmp_path, source, stdin, expected):
    program = parse(source)
    assert SemanticAnalyzer().analyze(program)
    cpp = tmp_path / 'program.cpp'
    cpp.write_text(CppCodeGenerator().render(program), encoding='utf-8')
    exe = tmp_path / ('program' + executable_suffix())
    built = compile_cpp(cpp, exe)
    assert built.returncode == 0, built.stderr
    ran = subprocess.run([str(exe)], input=stdin, capture_output=True, text=True,
                         timeout=10, env=runtime_environment())
    assert ran.returncode == 0, ran.stderr
    assert ran.stdout == expected


@pytest.mark.native
def test_cli_generates_tac_cpp_and_binary(tmp_path):
    source = tmp_path / 'smoke.minipar'
    source.write_text('print(42);', encoding='utf-8')
    built = subprocess.run([sys.executable, str(ROOT / 'main.py'), str(source)], cwd=tmp_path,
                           capture_output=True, text=True, timeout=120)
    assert built.returncode == 0, built.stderr
    assert (tmp_path / 'output/smoke.tac').read_text(encoding='utf-8') == 'print 42\n'
    assert '<< 42' in (tmp_path / 'output/smoke.cpp').read_text(encoding='utf-8')
    ran = subprocess.run([str(tmp_path / ('output/smoke' + executable_suffix()))],
                         capture_output=True, text=True, timeout=10, env=runtime_environment())
    assert (ran.returncode, ran.stdout) == (0, '42\n')


@pytest.mark.parametrize(('source', 'message'), [('print("bad', 'ERRO LEXICO'),
    ('print(1)', 'ERRO SINTATICO'), ('print(missing);', 'ERRO SEMANTICO')])
def test_cli_invalid_source_fails_before_native(tmp_path, source, message):
    path = tmp_path / 'bad.minipar'
    path.write_text(source, encoding='utf-8')
    ran = subprocess.run([sys.executable, str(ROOT / 'main.py'), str(path)], cwd=tmp_path,
                         capture_output=True, text=True, timeout=10)
    assert ran.returncode != 0 and message in ran.stderr
    assert not (tmp_path / 'output').exists()


@pytest.mark.native
def test_cpp_string_list_is_compiled_and_executed(parse, tmp_path):
    # Regressao da lacuna antiga: agora a lista conserva seu tipo string.
    program = parse('var names = ["a"]; print(names);')
    assert SemanticAnalyzer().analyze(program)
    cpp = tmp_path / 'bad.cpp'
    cpp.write_text(CppCodeGenerator().render(program), encoding='utf-8')
    built = compile_cpp(cpp, tmp_path / ('bad' + executable_suffix()))
    assert built.returncode == 0, built.stderr
    ran = subprocess.run([str(tmp_path / ('bad' + executable_suffix()))], capture_output=True,
                         text=True, timeout=10, env=runtime_environment())
    assert (ran.returncode, ran.stdout) == (0, '[a]\n')


@pytest.mark.native
def test_cpp_compilation_failure_is_reported(tmp_path):
    cpp = tmp_path / 'invalid.cpp'
    cpp.write_text('int main( {', encoding='utf-8')
    built = compile_cpp(cpp, tmp_path / ('invalid' + executable_suffix()))
    assert built.returncode != 0 and built.stderr


def test_explicit_missing_compiler_is_not_silently_replaced(monkeypatch):
    monkeypatch.setenv('MINIPAR_CXX', '/nonexistent/minipar-g++')
    with pytest.raises(ToolchainError, match='nao encontrado'):
        compiler_path()
