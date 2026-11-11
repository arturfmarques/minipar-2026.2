import pytest
from semantic import SemanticAnalyzer


@pytest.mark.parametrize(('source', 'message'), [
    ('return 1;', 'fora de funcao'), ('print(this);', 'fora de metodo'),
    ('var n = 1; n.no_method();', 'nao possui metodos'),
    ('class C {} var c = new C(); c.no_method();', 'nao declarado'),
    ('class C {} var c = new C(); print(c.no_field);', 'nao declarado'),
    ('func f(number n) -> number { return n; } f("bad");', 'Tipo incompativel'),
    ('func f() -> string { return 2; }', 'retorno'),
    ('func f() -> void { return 2; }', 'retorno'),
    ('func f(number n) -> number { if (n > 0) return n; }', 'todos os caminhos'),
    ('func f(x) { if (x) return 1; return "bad"; }', 'Retornos incompativeis'),
    ('var c = c_channel(1,7000);', 'host'),
    ('var c = c_channel("host","bad");', 'porta'),
    ('var c = c_channel("host",65536);', 'Porta'),
    ('send(1,"bad");', 'canal de send'),
    ('var s = receive("bad");', 'canal de receive'),
    ('var c = c_channel("host",7000); send(c,[1]);', 'mensagem escalar'),
    ('print(1 + "bad");', 'Operador'),
    ('print(-"bad");', 'unario'),
    ('print(true && "bad");', 'logico'),
    ('if ("bad") print(1);', 'Condicao'),
    ('var a = [1]; print(a["bad"]);', 'indice'),
    ('for (var x in 2) print(x);', 'For-in'),
    ('len();', 'espera'), ('exp("bad");', 'Tipo incompativel'),
    ('class A extends B {} class B extends A {}', 'Ciclo de heranca'),
    ('func f() {} func f() {}', 'ja declarada'),
    ('func f() {} var x = f();', 'void'),
    ('func f(x) { return x * 2; } f("bad");', 'Tipo incompativel'),
    ('func identity(x) { return x; } string bad = identity(2);', 'Tipo incompativel'),
    ('func identity(x) { return x; } var t = fork local identity(2); string bad = join(t);', 'Tipo incompativel'),
    ('func f() { return 2; } var t = fork local f(); var a = [t];', 'Lista nao pode'),
    ('if (true) var hidden = 2; print(hidden);', 'nao declarada'),
    ('while (false) var hidden = 2; print(hidden);', 'nao declarada'),
    ('func f() { par { return 2; } }', 'PAR inline'),
    ('func f() {} seq { var f = 1; f(); }', 'nao e funcao'),
    ('func f() {} seq { var f = 1; var t = fork local f(); }', 'sombreado'),
    ('func len(x) { return x; }', 'builtin'),
    ('func f(x) { return x + 2; } f("bad");', 'Tipo incompativel'),
    ('func f(a,b) { return a < b; } f(1,"bad");', 'Tipo incompativel'),
])
def test_semantic_invalid_programs(parse, source, message):
    analyzer = SemanticAnalyzer()
    assert not analyzer.analyze(parse(source))
    assert any(message in d.message for d in analyzer.diagnostics)
    assert all(d.line > 0 and d.col > 0 for d in analyzer.diagnostics)


@pytest.mark.parametrize('source', [
    'func fact(number n) -> number { if(n <= 1) return 1; return n * fact(n-1); } print(fact(5));',
    'func outer(number n) -> number { return inner(n); } func inner(number n) -> number { return n; } print(outer(3));',
    'class A { number value = 1; func get() -> number { return this.value; } } class B extends A {} var b = new B(); print(b.get());',
    'func f(number x) seq { return x; } print(f(2));',
    'var a = matrix(2,2,0); a[0][1] = 2;',
    'var a = [1]; a.append(2); print(a.size());',
    'func f(x) { seq { var x = "shadow"; print(x); } return x; } number result = f(2);',
    'func f(x) { var x = 2; return x * 2; } print(f("unused"));',
    'func compare(a,b) { return a < b; } print(compare("a","b"));',
])
def test_semantic_valid_programs(parse, source):
    analyzer = SemanticAnalyzer()
    assert analyzer.analyze(parse(source)), analyzer.diagnostics


def test_analyzer_can_be_reused_without_previous_errors(parse):
    analyzer = SemanticAnalyzer()
    assert not analyzer.analyze(parse('return 1;'))
    assert analyzer.analyze(parse('print(1);')) and not analyzer.diagnostics
