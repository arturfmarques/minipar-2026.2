import pytest
from semantic import SemanticAnalyzer


@pytest.mark.parametrize('source', [
    'bool ok=is_finite(42);',
    'bool written=try_write_text("output/a.arm",".arm");',
    'set_exit_code(2);',
])
def test_diagnostic_library_signatures(parse, source):
    analyzer = SemanticAnalyzer()
    assert analyzer.analyze(parse(source)), analyzer.diagnostics


@pytest.mark.parametrize('source', [
    'is_finite("42");', 'is_finite();', 'try_write_text(1,"x");',
    'try_write_text("x");', 'set_exit_code("2");', 'var x=set_exit_code(0);',
])
def test_diagnostic_library_rejects_invalid_calls(parse, source):
    analyzer = SemanticAnalyzer()
    assert not analyzer.analyze(parse(source))
    assert analyzer.diagnostics
