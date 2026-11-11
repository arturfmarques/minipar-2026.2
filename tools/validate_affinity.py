"""Valida os Testes 8-10 com afinidade opcional, sem alterar seus algoritmos."""
import argparse
import ast as literal_ast
import hashlib
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT),str(ROOT/'src')]
from lexer import Lexer, TokenType
from tools import validate_programs as pipeline
from tools import validate_parallel as parallel


def pin_source(source, cpus):
    """Acrescenta somente o sufixo aos forks locais reconhecidos pelo lexer."""
    tokens = Lexer(source).tokenize()
    offsets = [0]
    for line in source.splitlines(keepends=True): offsets.append(offsets[-1]+len(line))
    insertions, assignments = [], []
    for index, token in enumerate(tokens[:-1]):
        if token.type != TokenType.FORK or tokens[index+1].type != TokenType.LOCAL:
            continue
        name = tokens[index+2].lexeme
        depth = 0
        for end in range(index+3,len(tokens)):
            if tokens[end].type == TokenType.LPAREN: depth += 1
            elif tokens[end].type == TokenType.RPAREN:
                depth -= 1
                if depth == 0: break
        else:
            raise ValueError('Chamada fork sem fechamento')
        if len(assignments) >= len(cpus):
            raise ValueError('Quantidade insuficiente de processadores permitidos')
        cpu = cpus[len(assignments)]
        closing = tokens[end]
        offset = offsets[closing.line-1]+closing.col
        insertions.append((offset,f' on core({cpu})'))
        assignments.append({'function':name,'source_line':token.line,'logical_cpu':cpu})
    for offset, suffix in reversed(insertions): source = source[:offset]+suffix+source[offset:]
    return source, assignments


def records(path):
    return [dict(zip(('event','pid','task','micros','detail'),line.split('\t',4)))
            for line in path.read_text(encoding='utf-8').splitlines()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--program',type=int,choices=(8,9,10),action='append')
    parser.add_argument('--output',type=Path,default=Path('output/validation-affinity'))
    parser.add_argument('--report',type=Path,default=Path('output/validacoes/afinidade-8910.json'))
    args = parser.parse_args()
    directory = (ROOT/args.output).resolve()
    if not directory.is_relative_to(ROOT):
        parser.error('--output deve ficar dentro do repositorio, em output/')
    directory.mkdir(parents=True,exist_ok=True)
    probe_source = directory/'probe.minipar'
    probe_source.write_text('print(available_cpus());\n',encoding='utf-8')
    probe = pipeline.build(probe_source,directory/'probe')
    report = {'probe':probe,'cases':[], 'physical_cores_claimed':False}
    pipeline.save(ROOT/args.report,report)
    assert probe['phases']['native_compilation'] == pipeline.PASS, probe
    result = pipeline.run(probe)
    assert result.returncode == 0, result.stderr
    cpus = list(map(int,literal_ast.literal_eval(result.stdout)))
    report['allowed_logical_cpus'] = cpus
    for number in args.program or (8,9,10):
        source = parallel.SOURCES[number]
        count = number-4
        case = {'test':number,'source':source.relative_to(ROOT).as_posix(),
                'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'required_logical_cpus':count}
        report['cases'].append(case)
        if len(cpus)<count:
            case.update(status=pipeline.NOT_RUN,reason=f'Exige {count} CPUs permitidas; processo permite {len(cpus)}')
        else:
            try:
                target = directory/f'teste{number}'
                target.mkdir(exist_ok=True)
                text, assignments = pin_source(source.read_text(encoding='utf-8'),cpus[:count])
                assert len(assignments)==count, assignments
                generated = target/'program.minipar'
                generated.write_text(text,encoding='utf-8')
                built = pipeline.build(generated,target)
                case.update(assignments=assignments,build=built)
                assert built['phases']['native_compilation']==pipeline.PASS, built
                trace = target/'trace.tsv'
                if trace.exists(): trace.unlink()
                result = pipeline.run(built,env={'MINIPAR_TRACE':str(trace),'MINIPAR_REMOTE':'0','MINIPAR_WORK_FACTOR':'1'})
                assert result.returncode==0, result.stderr
                case['verified_results'] = parallel.validate(number,result.stdout,1)
                rows = records(trace)
                pins = [r for r in rows if r['event']=='affinity_applied']
                assert len(pins)==count, pins
                expected = {f'requested={cpu} actual={cpu}' for cpu in cpus[:count]}
                assert {r['detail'] for r in pins}==expected
                starts = [int(r['micros']) for r in rows if r['event']=='task_start']
                ends = [int(r['micros']) for r in rows if r['event']=='task_end']
                assert len(starts)==len(ends)==count and max(starts)<min(ends)
                case.update(status=pipeline.PASS,affinity_events=pins,trace=rows,
                            all_task_intervals_overlap=True,physical_cores_claimed=False)
            except Exception as error:
                case.update(status=pipeline.FAIL,error=str(error))
        pipeline.save(ROOT/args.report,report)
        print(number,case['status'],case.get('reason',case.get('error','')),flush=True)
    return 0 if all(c['status']==pipeline.PASS for c in report['cases']) else 1


if __name__=='__main__':
    sys.exit(main())
