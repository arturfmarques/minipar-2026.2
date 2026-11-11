"""Algoritmos MiniPar reais: compilacao instrumentada, resultados e TCP."""
import json
import math
from pathlib import Path
import random
import re
import socket
import subprocess
import pytest
from tools import validate_programs as validation
# Controladores de processos/framing ja exercitados pela suite anterior.
from test_runtime import Running, worker, listener, free_port, receive_frame, frame, send_channel, trace_records

ROOT = validation.ROOT
OBSERVATIONS = []
MATRIX = {'cases': []}
pytestmark = pytest.mark.native


def observe(name, **data):
    OBSERVATIONS.append({'test': name, **data})
    validation.save(ROOT / 'output/validacoes/testes-1a7-casos.json', OBSERVATIONS)


@pytest.fixture(scope='module')
def originals(tmp_path_factory):
    built = {}
    for number, source in validation.SOURCES.items():
        record = validation.build(source, tmp_path_factory.mktemp(f'original{number}'))
        record['test'] = number
        MATRIX['cases'].append(record)
        validation.save(ROOT / 'output/validacoes/validacao-1a7.json', MATRIX)
        assert record['phases']['native_compilation'] == validation.PASS, record
        built[number] = record
    return built


@pytest.mark.parametrize('number', range(1, 8))
def test_original_full_pipeline_and_mathematical_results(originals, number):
    record = originals[number]
    result = validation.run(record, validation.inputs(number))
    try:
        assert result.returncode == 0, result.stderr
        validation.validate(number, result.stdout)
        record['phases']['results'] = validation.PASS
        record['final'] = validation.PASS
    except AssertionError:
        record['phases']['results'] = validation.FAIL
        record['final'] = validation.FAIL
        raise
    finally:
        validation.save(ROOT / 'output/validacoes/validacao-1a7.json', MATRIX)


DRIVERS = {
    'sort6': 'var a = parse_ints(input()); var q = new Quicksort(); q.carregar(a); print("SORT:", q.ordenar());',
    'sort7': 'var a = parse_ints(input()); print("SORT:", quicksort_iterativo(a));',
    'neuron': '''var entrada = to_number(input()); var desejado = to_number(input());
        var peso = to_number(input()); var pb = to_number(input()); var taxa = to_number(input());
        var n = new Neuronio(entrada, desejado, peso, pb, taxa);
        print("BOUNDARY:", n.ativacao(0)); n.treinar();''',
    'xor': '''var rede = new RedeNeuralXOR();
        print("BEFORE:", rede.feedforward(0,0), rede.feedforward(0,1), rede.feedforward(1,0), rede.feedforward(1,1));
        print("WEIGHT_BEFORE:", rede.h1_w1); rede.treinar();
        print("WEIGHT_AFTER:", rede.h1_w1); rede.testar();''',
    'forward': '''var x1 = to_number(input()); var x2 = to_number(input());
        var w1 = to_number(input()); var b1 = to_number(input());
        var w2 = to_number(input()); var b2 = to_number(input());
        var rede = new RedeNeural(2,3,2);
        for (var i in range(2)) { for (var j in range(3)) { rede.W1[i][j] = w1; } }
        for (var i in range(3)) { rede.b1[i] = b1; for (var j in range(2)) { rede.W2[i][j] = w2; } }
        for (var i in range(2)) { rede.b2[i] = b2; }
        rede.W2[0][1] = w2 + 0.25;
        print("SHAPE:", len(rede.W1), len(rede.W1[0]), len(rede.W2), len(rede.W2[0]));
        print("FORWARD:", rede.forward([x1,x2]));''',
    'calculator_remote': '''var porta_worker = to_number(input());
        var req = c_channel("127.0.0.1", to_number(input()));
        var res = c_channel("127.0.0.1", to_number(input()));
        var op = input(); var a = input(); var b = input();
        var tarefa = fork remote("127.0.0.1", porta_worker) servidor(req, res);
        send(req, op); send(req, a); send(req, b);
        print("Resultado:", receive(res)); join(tarefa);''',
    'parallel': '''var n = to_number(input()); var limite = to_number(input());
        var p1 = to_number(input()); var g1 = to_number(input());
        var p2 = to_number(input()); var g2 = to_number(input());
        par {
            seq {
                if(p1 > 0) { var ready = c_channel("127.0.0.1",p1); var gate = c_channel("127.0.0.1",g1);
                    send(ready,"fat_ready"); var release = receive(gate); }
                print("FAT:",fatorial(n));
            }
            seq {
                if(p2 > 0) { var ready = c_channel("127.0.0.1",p2); var gate = c_channel("127.0.0.1",g2);
                    send(ready,"fib_ready"); var release = receive(gate); }
                print("FIB:",fibonacci(limite));
            }
        }''',
    'guards': '''class Counter { number value=0;
            func init(number value) { this.value=value; }
            func bump() -> number { this.value=this.value+1; return this.value; }
        }
        class Derived extends Counter {}
        var mode = input();
        if(mode == "negative") { var a=[1]; print(a[-1]); }
        if(mode == "fractional") { var a=[1,2]; print(a[0.5]); }
        if(mode == "past_end") { var a=[1]; a[1]=2; }
        if(mode == "matrix") { var a=matrix(2,2,0); a[1][2]=1; }
        if(mode == "pop") { var a=[]; print(a.pop()); }
        if(mode == "divide") { print(1/0); }
        if(mode == "numeric") { var a=1; a=a+0.5; var total=0;
            for(var v=0; v<1; v=v+0.5) { total=total+v; }
            print(a,5/2,len([])-1,[].size()-1,total,50000*50000); }
        if(mode == "objects") { var a=[new Derived(3),new Derived(8)]; print(a[0].bump(),a[1].bump()); }
        if(mode == "strings") { var a=["a","b"]; a.clear(); a.append("c"); print(a); }
        if(mode == "parse") { print(parse_ints(input())); }''',
}


@pytest.fixture(scope='module')
def drivers(tmp_path_factory):
    built = {}
    numbers = {'sort6': 6, 'sort7': 7, 'neuron': 3, 'xor': 4, 'forward': 5,
               'calculator_remote': 1, 'parallel': 2, 'guards': 7}
    for name, main in DRIVERS.items():
        record = validation.build(validation.SOURCES[numbers[name]], tmp_path_factory.mktemp(name), main=main)
        observe('build_driver', driver=name, record=record)
        assert record['phases']['native_compilation'] == validation.PASS, record
        built[name] = record
    return built


def execute(record, stdin, expected_success=True):
    result = validation.run(record, stdin)
    observe('execution', source=record['file'], main=record['main_override'], **record['execution'])
    assert result.returncode == (0 if expected_success else 1), result.stderr
    return result.stdout, result.stderr


SORT_CASES = [[], [42], [1,2,3,4,5], [5,4,3,2,1], [-7,0,-1,-50,3], [3,3,1,3,1],
              [33,12,98,5,61], [10,-3,-40,80,70,-100], list(range(257,-1,-1)),
              random.Random(2026).choices(range(-1000,1001), k=193)]


@pytest.mark.parametrize('algorithm', ['sort6','sort7'])
@pytest.mark.parametrize('values', SORT_CASES, ids=['empty','single','ordered','reverse','negative','duplicates','required7','required6','large','seeded'])
def test_quicksort_varied_inputs_without_fixed_outputs(drivers, algorithm, values):
    stdout, stderr = execute(drivers[algorithm], ' '.join(map(str,values))+'\n')
    assert validation.vector_after(stdout,'SORT:') == sorted(values)
    assert not stderr  # inclui verificacoes _GLIBCXX_ASSERTIONS


OPERATIONS = [('+',2,3,5),('-',-4,7,-11),('*',-3,2.5,-7.5),('/',7,2,3.5),('/',1,0,None)]


@pytest.mark.parametrize(('op','a','b','expected'), OPERATIONS)
def test_calculator_messages_and_zero_division(originals,op,a,b,expected):
    stdout, _ = execute(originals[1], f'{op}\n{a}\n{b}\n')
    if expected is None: assert 'Resultado: ERRO: divisao por zero' in stdout
    else: assert math.isclose(float(re.search(r'Resultado:\s*([^\n]+)',stdout)[1]),expected)


@pytest.mark.parametrize(('op','a','b','expected'), OPERATIONS)
def test_calculator_server_in_another_process(drivers,tmp_path,op,a,b,expected):
    binary=Path(drivers['calculator_remote']['executable'])
    with worker(binary,tmp_path) as (remote,ready,trace):
        stdout, _ = execute(drivers['calculator_remote'],f'{ready["port"]}\n{free_port()}\n{free_port()}\n{op}\n{a}\n{b}\n')
        if expected is None: assert 'Resultado: ERRO: divisao por zero' in stdout
        else: assert math.isclose(float(re.search(r'Resultado:\s*([^\n]+)',stdout)[1]),expected)
        assert remote.finish()[0] == 0
        events=trace_records(trace)
        assert any(e['event']=='worker_end' and e['detail']=='servidor' for e in events)
        observe('calculator_other_process',worker=ready,events=events,stdout=stdout)


@pytest.mark.parametrize(('n','limit'),[(0,0),(1,1),(5,8),(8,15),(10,20)])
def test_parallel_factorial_and_fibonacci_math(drivers,n,limit):
    stdout,_=execute(drivers['parallel'],f'{n}\n{limit}\n0\n0\n0\n0\n')
    assert float(re.search(r'FAT:\s*([^\n]+)',stdout)[1]) == math.factorial(n)
    expected=[]; a,b=0,1
    for _ in range(limit): expected.append(a); a,b=b,a+b
    assert validation.vector_after(stdout,'FIB:') == expected


def test_test2_par_tasks_overlap_with_barriers(drivers,tmp_path):
    trace=tmp_path/'par.tsv'
    with listener() as ready1, listener() as ready2:
        gates=[free_port(),free_port()]
        running=Running([drivers['parallel']['executable']],
                        [8,15,ready1.getsockname()[1],gates[0],ready2.getsockname()[1],gates[1]],
                        extra={'MINIPAR_TRACE':str(trace)})
        try:
            for sock,expected in [(ready1,b'fat_ready'),(ready2,b'fib_ready')]:
                connection,_=sock.accept()
                with connection:
                    assert receive_frame(connection)==expected; frame(connection,b'OK')
            assert running.process.poll() is None
            for gate in gates: send_channel(gate,b'release')
            code,stdout,stderr=running.finish()
            assert code==0,stderr
            assert 'FAT: 40320' in stdout and len(validation.vector_after(stdout,'FIB:'))==15
            events=trace_records(trace)
            starts=[int(e['micros']) for e in events if e['event']=='task_start']
            ends=[int(e['micros']) for e in events if e['event']=='task_end']
            assert len(starts)==len(ends)==2 and max(starts)<min(ends)
            observe('test2_overlap',events=events,barrier=True,stdout=stdout)
        finally: running.stop()


@pytest.mark.parametrize('parameters',[(1,0,.5,.5,.01),(1,1,-.3,-.2,.1),(0,0,.7,.2,.05),(-1,1,.2,-.1,.05)])
def test_neuron_constructor_activation_training_and_updates(drivers,parameters):
    stdout,_=execute(drivers['neuron'],'\n'.join(map(str,parameters))+'\n')
    assert 'BOUNDARY: 1' in stdout  # >= 0 oficial, nao > 0
    iteration,weight,bias=validation.neuron_oracle(*parameters)
    assert int(re.search(r'Iteracoes totais:\s*(\d+)',stdout)[1])==iteration
    assert math.isclose(float(re.search(r'Peso final:\s*([^\n]+)',stdout)[1]),weight,abs_tol=1e-6)
    assert math.isclose(float(re.search(r'Peso bias final:\s*([^\n]+)',stdout)[1]),bias,abs_tol=1e-6)
    assert re.findall(r'Erro:\s*([^\n]+)',stdout)[-1]=='0'


def test_xor_reproducible_learning_changes_weights_and_reduces_loss(drivers):
    first,_=execute(drivers['xor'],'')
    second,_=execute(drivers['xor'],'')
    assert first==second
    validation.validate(4,first)
    before=list(map(float,re.search(r'BEFORE:\s*([^\n]+)',first)[1].split()))
    after=[float(v) for v in re.findall(r'Predicted Output:\s*([^\n]+)',first)]
    mse=lambda values: sum((a-b)**2 for a,b in zip(values,[0,1,1,0]))/4
    assert mse(before)>.2 and mse(after)<.005
    assert re.search(r'WEIGHT_BEFORE:\s*([^\n]+)',first)[1] != re.search(r'WEIGHT_AFTER:\s*([^\n]+)',first)[1]
    observe('xor_learning',mse_before=mse(before),mse_after=mse(after),predictions=after)


@pytest.mark.parametrize('history',[validation.HISTORY,[0]*16,[1]*16,[0,1]*8])
def test_recommendations_match_official_model_and_exclude_purchases(originals,history):
    stdout,_=execute(originals[5],'\n'.join(map(str,history))+'\n')
    validation.validate(5,stdout,history)
    if history==validation.HISTORY:
        expected=(ROOT/'tests/expected_results/teste5_recomendacao.expected.txt').read_text(encoding='utf-8').splitlines()[1:]
        assert stdout.split('Produtos recomendados para você:\n')[1].splitlines()==expected


@pytest.mark.parametrize('values',[(0,0,.5,.5,.5,.5),(1,0,-2,-1,.4,-.2),(1,1,.2,-.1,-.5,.3),(-2,3,.7,.1,0,-.5)])
def test_recommendation_network_really_uses_matrix_weights_bias_relu_and_sigmoid(drivers,values):
    stdout,_=execute(drivers['forward'],'\n'.join(map(str,values))+'\n')
    assert 'SHAPE: 2 3 3 2' in stdout
    x1,x2,w1,b1,w2,b2=values
    hidden=max(0,(x1+x2)*w1+b1)
    sigmoid=lambda x: 1/(1+math.exp(-x))
    expected=[sigmoid(3*hidden*w2+b2),sigmoid(3*hidden*w2+.25*hidden+b2)]
    assert validation.vector_after(stdout,'FORWARD:')==pytest.approx(expected,abs=5e-6)


@pytest.mark.parametrize('mode',['negative','fractional','past_end','matrix','pop','divide','parse'])
def test_invalid_native_inputs_are_diagnosed_without_memory_corruption(drivers,mode):
    stdout,stderr=execute(drivers['guards'],mode+'\n1 bad 2\n',expected_success=False)
    assert not stdout and '[ERRO RUNTIME]' in stderr
    assert any(word in stderr for word in ['Indice','pop','Divisao','parse_ints'])


def test_numeric_values_lengths_and_string_lists_keep_their_types(drivers):
    stdout,_=execute(drivers['guards'],'numeric\n')
    assert list(map(float,stdout.split()))==[1.5,2.5,-1,-1,0.5,2500000000]
    stdout,_=execute(drivers['guards'],'strings\n')
    assert stdout=='[c]\n'
    stdout,_=execute(drivers['guards'],'objects\n')
    assert stdout=='4 9\n'


def test_original_bug_is_reported_instead_of_corrupting_memory(tmp_path):
    source=ROOT/'tests/fixtures/originais-2026-1/teste7_quicksort_iterativo_tac.minipar'
    record=validation.build(source,tmp_path)
    assert record['phases']['native_compilation']==validation.PASS,record
    stdout,stderr=execute(record,'',expected_success=False)
    assert not stdout and 'Indice fora dos limites' in stderr and 'tamanho=2' in stderr
    observe('original_stack_bug_checked',**record['execution'])


@pytest.mark.parametrize('name',['teste_adicional1_paralelismo_3_computadores',
    'teste_adicional2_tapete_sierpinski','teste_ascii_art_divertidapkrl','teste_bnf_controles_input'])
def test_four_legacy_additional_examples_keep_their_behavior(tmp_path,name):
    record=validation.build(ROOT/'tests'/f'{name}.minipar',tmp_path)
    assert record['phases']['native_compilation']==validation.PASS,record
    stdout,stderr=execute(record,'')
    assert not stderr
    if name=='teste_adicional1_paralelismo_3_computadores':
        # Prototipo antigo transmite resumos constantes; nao comprova 3 computadores.
        assert 'PC1 QuickSort: [33,12,98,5,61] -> [5,12,33,61,98]' in stdout
        assert 'PC2 Matrizes: [[1,2],[3,4]] x [[5,6],[7,8]] -> [[19,22],[43,50]]' in stdout
        assert 'PC3 Fatorial: 5! = 120' in stdout
    elif name=='teste_adicional2_tapete_sierpinski':
        rows=[line[1:-1].split(', ') for line in stdout.splitlines() if line.startswith('[')]
        assert len(rows)==9 and all(len(row)==9 for row in rows)
        for r,row in enumerate(rows):
            for c,value in enumerate(row):
                hole=(r%3==c%3==1) or (r//3==c//3==1)
                assert value==(' ' if hole else '#')
    elif name=='teste_ascii_art_divertidapkrl':
        rows=[line[1:-1].split(', ') for line in stdout.splitlines() if line.startswith('[')]
        expected=[[' ']*64 for _ in range(32)]; expected[0][31]='A'
        for i in range(1,32):
            for j in range(1,63):
                if (expected[i-1][j-1]=='A') != (expected[i-1][j+1]=='A'): expected[i][j]='A'
        assert rows==expected
    else:
        assert stdout=='Controle OK: 7 2\n'
    record['phases']['results']=validation.PASS
    observe('additional_regression',record=record)
