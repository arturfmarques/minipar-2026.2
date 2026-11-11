import re
import pytest
from lexer import Lexer
from parser import Parser
from semantic import SemanticAnalyzer
from tac import TACGenerator
from tools.validate_programs import SOURCES, tac_contract


@pytest.mark.parametrize('number', range(1,8))
def test_real_program_tac_has_control_flow_calls_and_data_operations(number):
    program=Parser(Lexer(SOURCES[number].read_text(encoding='utf-8')).tokenize()).parse()
    analyzer=SemanticAnalyzer()
    assert analyzer.analyze(program), analyzer.diagnostics
    text=TACGenerator().generate_text(program)
    checks=tac_contract(program,text)
    assert checks['temporaries']>0 and checks['calls']>0 and checks['jumps']>0
    if number==1:
        for op in ('+', '-', '*', '/'):
            assert re.search(r'= \w+ '+re.escape(op)+r' \w+',text)
        assert 'receive ' in text and 'send ' in text and '= spawn ' in text
    if number==2:
        assert 'func fatorial:' in text and 'func fibonacci:' in text
        assert text.count('= spawn ')==2 and 'WHILE_' in text
    if number in (3,4,5):
        assert 'class ' in text and 'field_addr' in text and 'callmethod ' in text
    if number==3:
        assert ' >= ' in text and ' * ' in text and 'store ' in text
    if number==4:
        assert 'call exp,' in text and 'func RedeNeuralXOR.treinar_amostra:' in text
    if number==5:
        assert 'class Produto' in text and 'class Categoria' in text and 'class Usuario' in text
        assert 'iter_has_next' in text and re.search(r'= [\w@.]+\[[\w@.]+\]',text) and 'load_ref' in text
    if number==6:
        function=text.split('func Quicksort.quicksort:',1)[1].split('endfunc Quicksort.quicksort',1)[0]
        assert len(re.findall(r'callmethod \w+, quicksort, 2',function))==2
        assert 'index_addr' in text and 'store ' in text
    if number==7:
        assert 'call quicksort_iterativo, 1' in text
        assert ', pop, 0' in text and text.count(', append, 1')==4
        assert 'index_addr' in text and 'WHILE_' in text


def test_quicksort_named_function_and_renaming_both_follow_ast():
    def tac(name, value):
        source=f'func {name}(a) {{ a.append({value}); return a; }} var a=[1]; print({name}(a));'
        return TACGenerator().generate_text(Parser(Lexer(source).tokenize()).parse())
    first=tac('quicksort_iterativo',11)
    second=tac('quicksort_iterativo',23)
    other=tac('qualquer_nome',11)
    assert first!=second and ' = 11' in first and ' = 23' in second
    assert first.replace('quicksort_iterativo','qualquer_nome')==other


def test_mutating_methods_use_original_receiver_references():
    source='class C { var values=[1]; } var a=[1]; a.append(2); var c=new C(); c.values.clear();'
    text=TACGenerator().generate_text(Parser(Lexer(source).tokenize()).parse())
    assert '= ref a' in text and 'field_addr c, values' in text and '= load_ref ' in text
