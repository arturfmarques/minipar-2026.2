"""Oraculos independentes para treinamento manual e estado de objetos MiniPar."""
import math
import random
from pathlib import Path
import pytest
from tools import validate_programs as validation

pytestmark=pytest.mark.native
ROOT=Path(__file__).resolve().parents[2]
FIELDS=[f'h{i}_{suffix}' for i in (1,2,3) for suffix in ('w1','w2','bias')]+['out_w1','out_w2','out_w3','out_bias']

XOR_MAIN = ('var rede=new RedeNeuralXOR(); var other=new RedeNeuralXOR(); '
    'rede.taxa_aprendizado=to_number(input()); '
    + ' '.join(f'rede.{name}=to_number(input());' for name in FIELDS)
    + ' var x1=to_number(input()); var x2=to_number(input()); var target=to_number(input()); '
    'print("FORWARD:",to_string(rede.feedforward(x1,x2)),to_string(rede.h1),to_string(rede.h2),to_string(rede.h3)); '
    'print("OTHER_BEFORE:",to_string(other.feedforward(x1,x2))); '
    'rede.treinar_amostra(x1,x2,target); '
    + ' '.join(f'print("STATE:",to_string(rede.{name}));' for name in FIELDS)
    + ' print("OTHER_AFTER:",to_string(other.feedforward(x1,x2)));')
DRIVERS={
    4:XOR_MAIN,
    3:'var a=new Neuronio(1,0,0.5,0.5,0.01); var b=new Neuronio(1,1,0.75,0.25,0.05); a.treinar(); print("STATE:",to_string(a.peso),to_string(a.peso_bias),to_string(b.peso),to_string(b.peso_bias));',
    5:'var a=new RedeNeural(2,3,2); var b=new RedeNeural(2,3,2); a.W1[0][0]=2; a.b1[0]=0; print("A:",a.forward([1,0])); print("B:",b.forward([1,0])); print("FIELD:",a.W1[0][0],b.W1[0][0]); var u=new Usuario(["A"]); var v=new Usuario(["B"]); print("U:",u.codificar_historico(["A","B"])); print("V:",v.codificar_historico(["A","B"]));',
    6:'var a=new Quicksort(); var b=new Quicksort(); a.carregar([3,1,2]); b.carregar([8,7]); print("A:",a.ordenar()); print("B_BEFORE:",b.array); print("B_AFTER:",b.ordenar()); print("A_AFTER:",a.array);',
}

@pytest.fixture(scope='module')
def object_binaries(tmp_path_factory):
    result={}
    for number,main in DRIVERS.items():
        record=validation.build(validation.SOURCES[number],tmp_path_factory.mktemp(f'oo{number}'),main=main)
        assert record['phases']['native_compilation']==validation.PASS,record
        result[number]=record
    return result


def forward(weights,inputs):
    sigmoid=lambda n:1/(1+math.exp(-n))
    hidden=[sigmoid(weights[3*i]*inputs[0]+weights[3*i+1]*inputs[1]+weights[3*i+2]) for i in range(3)]
    return sigmoid(sum(weights[9+i]*hidden[i] for i in range(3))+weights[12]),hidden

DEFAULT=[.2,-.4,0,-.3,.6,.1,.7,.5,-.2,.4,-.5,.3,0]
VARIED=[random.Random(2026+i).uniform(-.8,.8) for i in range(13)]

@pytest.mark.parametrize(('weights','inputs','target'),[
    (DEFAULT,(0,1),1),(VARIED,(1,0),1),(VARIED,(.25,.75),.4),
])
@pytest.mark.parametrize('rate',[.2,.5])
def test_each_xor_weight_and_bias_matches_numerical_gradient(object_binaries,weights,inputs,target,rate):
    stdin='\n'.join(map(str,[rate,*weights,*inputs,target]))+'\n'
    ran=validation.run(object_binaries[4],stdin); assert ran.returncode==0,ran.stderr
    lines=ran.stdout.splitlines()
    observed=list(map(float,next(s for s in lines if s.startswith('FORWARD:')).split()[1:]))
    expected,hidden=forward(weights,inputs)
    assert observed==pytest.approx([expected,*hidden],abs=1e-12)
    after=[float(s.split()[1]) for s in lines if s.startswith('STATE:')]
    loss=lambda values:.5*(forward(values,inputs)[0]-target)**2
    gradients=[]
    for index in range(len(weights)):
        plus=weights.copy();minus=weights.copy();plus[index]+=1e-6;minus[index]-=1e-6
        gradients.append((loss(plus)-loss(minus))/2e-6)
    assert after==pytest.approx([w-rate*g for w,g in zip(weights,gradients)],abs=2e-10)
    assert loss(after)<loss(weights)
    other=[float(s.split()[1]) for s in lines if s.startswith(('OTHER_BEFORE:','OTHER_AFTER:'))]
    assert other[0]==other[1]  # somente o objeto treinado muda


def test_neuron_instances_have_independent_constructor_and_training_state(object_binaries):
    ran=validation.run(object_binaries[3]);assert ran.returncode==0,ran.stderr
    values=list(map(float,next(s for s in ran.stdout.splitlines() if s.startswith('STATE:')).split()[1:]))
    _,weight,bias=validation.neuron_oracle(1,0,.5,.5,.01)
    assert values==pytest.approx([weight,bias,.75,.25],abs=1e-12)


def test_recommendation_network_and_user_instances_are_independent(object_binaries):
    ran=validation.run(object_binaries[5]);assert ran.returncode==0,ran.stderr
    sigmoid=lambda n:1/(1+math.exp(-n))
    assert validation.vector_after(ran.stdout,'A:')==pytest.approx([sigmoid(2.5)]*2,abs=5e-6)
    assert validation.vector_after(ran.stdout,'B:')==pytest.approx([sigmoid(2)]*2,abs=5e-6)
    assert 'FIELD: 2 0.5' in ran.stdout
    assert validation.vector_after(ran.stdout,'U:')==[1,0]
    assert validation.vector_after(ran.stdout,'V:')==[0,1]


def test_quicksort_uses_instance_arrays_methods_and_recursion(object_binaries):
    ran=validation.run(object_binaries[6]);assert ran.returncode==0,ran.stderr
    for label,expected in [('A:',[1,2,3]),('B_BEFORE:',[8,7]),('B_AFTER:',[7,8]),('A_AFTER:',[1,2,3])]:
        assert validation.vector_after(ran.stdout,label)==expected
