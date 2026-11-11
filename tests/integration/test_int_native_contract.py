import subprocess
import math
from decimal import Decimal
from pathlib import Path
import pytest
from lexer import Lexer
from parser import Parser
from semantic import SemanticAnalyzer
from codegen import CppCodeGenerator
from toolchain import compile_cpp, executable_suffix, runtime_environment
from test_runtime import worker, free_port

pytestmark=pytest.mark.native

SOURCE = """
func increment(int n)->int { return n+1; }
func recur(int n)->int { if(n==0) { return 1; } return n*recur(n-1); }
class Counter {
    int value=9007199254740993;
    func init(int n) { this.value=n; }
    func add(int n)->int { this.value=this.value+n; return this.value; }
}
var mode=input();
if(mode=="exact") { int n=9007199254740993; var copy=n; print(n,copy,increment(n),recur(5),n==9007199254740992,n>9007199254740992); }
if(mode=="bounds") { int a=-9223372036854775808; int b=9223372036854775807; print(a,b); }
if(mode=="ops") { int a=-7; int b=3; print(a+b,a-b,a*b,a%b,b%a,a/b); }
if(mode=="objects") { var a=new Counter(9007199254740993); var b=new Counter(10); print(a.add(1),b.add(2)); }
if(mode=="local") { var t=fork local increment(9007199254740993); print(join(t)); }
if(mode=="remote") { var t=fork remote("127.0.0.1",to_number(input())) increment(9007199254740993); print(join(t)); }
if(mode=="overflow") { int n=9223372036854775807; print(n+1); }
if(mode=="underflow") { int n=-9223372036854775808; print(n-1); }
if(mode=="negate") { int n=-9223372036854775808; print(-n); }
if(mode=="multiply") { int n=9223372036854775807; print(n*2); }
if(mode=="modzero") { int n=2; int z=0; print(n%z); }
if(mode=="fraction") { int n=to_number(input()); print(n); }
if(mode=="argument") { print(increment(to_number(input()))); }
if(mode=="return") { print(convert(to_number(input()))); }
if(mode=="legacy") { var n=1; n=n+0.5; print(n,5/2,50000*50000); }
func convert(number n)->int { return n; }
"""

@pytest.fixture(scope='module')
def integer_binary(tmp_path_factory):
    directory=tmp_path_factory.mktemp('int_contract')
    tree=Parser(Lexer(SOURCE).tokenize()).parse(); analyzer=SemanticAnalyzer()
    assert analyzer.analyze(tree), analyzer.diagnostics
    cpp=directory/'program.cpp'; cpp.write_text(CppCodeGenerator(analyzer).render(tree),encoding='utf-8')
    binary=directory/('program'+executable_suffix()); built=compile_cpp(cpp,binary)
    assert built.returncode==0, built.stderr
    return binary

@pytest.mark.parametrize(('mode','expected'),[
    ('exact','9007199254740993 9007199254740993 9007199254740994 120 0 1'),
    ('bounds','-9223372036854775808 9223372036854775807'),
    ('ops','-4 -10 -21 2 -4 -2.3333333333333335'),
    ('objects','9007199254740994 12'), ('local','9007199254740994'),
    ('legacy','1.5 2.5 2500000000'),
])
def test_int_real_arithmetic_objects_and_tasks(integer_binary,mode,expected):
    result=subprocess.run([str(integer_binary)],input=mode+'\n',capture_output=True,text=True,env=runtime_environment(),timeout=15)
    assert result.returncode==0 and not result.stderr
    actual=result.stdout.split(); wanted=expected.split()
    assert len(actual)==len(wanted)
    for value, reference in zip(actual,wanted):
        if Decimal(reference)==Decimal(reference).to_integral_value():
            assert Decimal(value)==Decimal(reference)  # exact, inclusive acima de 2**53
        else:
            assert math.isclose(float(value),float(reference),rel_tol=5e-6)  # cout legado: 6 digitos


@pytest.mark.parametrize('mode',['overflow','underflow','negate','multiply','modzero','fraction','argument','return'])
def test_invalid_dynamic_int_fails_without_truncation(integer_binary,mode):
    result=subprocess.run([str(integer_binary)],input=mode+'\n1.5\n',capture_output=True,text=True,env=runtime_environment(),timeout=15)
    assert result.returncode==1 and ('int' in result.stderr or 'Overflow' in result.stderr)


def test_int64_remote_roundtrip_is_exact(integer_binary,tmp_path):
    with worker(integer_binary,tmp_path) as (_,ready,_):
        result=subprocess.run([str(integer_binary)],input=f'remote\n{ready["port"]}\n',capture_output=True,text=True,env=runtime_environment(),timeout=15)
        assert (result.returncode,result.stdout.strip(),result.stderr)==(0,'9007199254740994','')
