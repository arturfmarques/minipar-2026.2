import pytest
from semantic import SemanticAnalyzer


@pytest.mark.parametrize('source', [
    'class C { number x = 0; func init(number x) { this.x = x; } } var c = new C(2);',
    'class C { func init() {} } class D extends C {} var d = new D();',
    'var a = ["a", "b"]; a.clear(); a.append("c");',
    'var a = [[1,2],[3,4]]; print(a[0][1]);',
])
def test_valid_constructor_and_collection_types(parse, source):
    analyzer = SemanticAnalyzer()
    assert analyzer.analyze(parse(source)), analyzer.diagnostics


@pytest.mark.parametrize(('source', 'message'), [
    ('class C { func init(number x) {} } var c = new C();', 'Construtor'),
    ('class C { func init(number x) {} } var c = new C("bad");', 'Tipo incompativel'),
    ('class C { func init() -> number { return 1; } } var c = new C();', 'init deve retornar void'),
    ('class C {} var c = new C(1);', 'Construtor padrao'),
    ('var a = [1, "bad"];', 'tipos compativeis'),
    ('var a = [1]; a.clear(1);', 'invalida'),
    ('var a = [1]; par { a.clear(); }', 'escopo externo'),
])
def test_invalid_constructor_and_collection_types(parse, source, message):
    analyzer = SemanticAnalyzer()
    assert not analyzer.analyze(parse(source))
    assert any(message in diagnostic.message for diagnostic in analyzer.diagnostics)
