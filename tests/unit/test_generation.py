import pytest
from codegen import CppCodeGenerator
from tac import TACGenerator
from toolchain import compile_command, executable_suffix


def test_tac_precedence_and_source_changes(parse):
    first = TACGenerator().generate_text(parse('var x = 2 + 3 * 4; print(x);'))
    assert first.splitlines() == ['t0 = 3 * 4', 't1 = 2 + t0', 'x = t1', 'print x']
    second = TACGenerator().generate_text(parse('var x = 2 + 3 * 5; print(x);'))
    assert second != first and '3 * 5' in second


def test_cpp_generated_from_ast(parse):
    first = CppCodeGenerator().render(parse('seq { print(2 + 3 * 4); }'))
    second = CppCodeGenerator().render(parse('seq { print(99); }'))
    assert 'int main(int argc, char** argv)' in first
    assert '(2.0 + (3.0 * 4.0))' in first
    assert first != second and '<< 99' in second


def test_native_flags_match_platform(tmp_path):
    source, exe = tmp_path / 'code.cpp', tmp_path / 'code'
    assert '-lws2_32' in compile_command(source, exe, 'g++', 'win32')
    assert '-lws2_32' not in compile_command(source, exe, 'g++', 'linux')
    assert '-std=c++20' in compile_command(source, exe, 'g++', 'linux')
    assert executable_suffix('win32') == '.exe'
    assert executable_suffix('linux') == ''


def test_known_quicksort_tac_must_depend_on_body(parse):
    a = TACGenerator().generate_text(parse('func quicksort_iterativo() { print(1); }'))
    b = TACGenerator().generate_text(parse('func quicksort_iterativo() { print(2); }'))
    assert a != b
