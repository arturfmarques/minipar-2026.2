import pytest
from semantic import SemanticAnalyzer
from codegen import CppCodeGenerator
from tac import TACGenerator


@pytest.mark.parametrize('source', [
    'int n=1.5;', 'int n=1; n=2.5;', 'int n=9223372036854775808;',
    'int n=-9223372036854775809;', 'int n=true;', 'int n="3";',
    'func f(int n) {} f(1.5);', 'func f()->int { return 1.5; }',
    'class C { int n=1; } var c=new C(); c.n=2.5;',
    'class C { func init(int n) {} } var c=new C(1.5);',
    'class C { func f(int n) {} } var c=new C(); c.f(1.5);',
])
def test_invalid_int_values_have_semantic_location(parse, source):
    analyzer=SemanticAnalyzer()
    assert not analyzer.analyze(parse(source))
    assert any('Tipo incompativel' in d.message and d.line >= 1 and d.col >= 1 for d in analyzer.diagnostics)


def test_int_frontend_symbols_tac_and_cpp_share_contract(parse):
    tree=parse('int n=9007199254740993; n=n+1; print(n);')
    analyzer=SemanticAnalyzer()
    assert analyzer.analyze(tree), analyzer.diagnostics
    assert tree.statements[0].type == tree.statements[0].symbol.type == 'int'
    tac=TACGenerator().generate_text(tree)
    assert '9007199254740993' in tac and '+' in tac
    cpp=CppCodeGenerator(analyzer).render(tree)
    assert 'std::int64_t n' in cpp and '__minipar_int_add' in cpp


def test_negative_decimal_keeps_number_promotion_in_mixed_expression(parse):
    tree=parse('int n=4; var a=n+2.0; var b=n+(-2.0);')
    analyzer=SemanticAnalyzer()
    assert analyzer.analyze(tree), analyzer.diagnostics
    assert tree.statements[1].symbol.type == tree.statements[2].symbol.type == 'number'
    cpp=CppCodeGenerator(analyzer).render(tree)
    assert 'double a' in cpp and 'double b' in cpp
