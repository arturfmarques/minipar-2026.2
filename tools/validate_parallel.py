"""Compila e verifica os programas MiniPar 8-10; Python apenas observa/oracula."""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import platform
from pathlib import Path
import re
import sys
import subprocess
from datetime import datetime, timezone
import xml.etree.ElementTree as ET
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools import validate_programs as pipeline

ROOT=pipeline.ROOT
SOURCES={8: ROOT/'tests/teste8_avaliacao_paralela.minipar',
         9: ROOT/'tests/teste9_avaliacao_mandelbrot.minipar',
         10:ROOT/'tests/teste10_avaliacao_fractais.minipar'}
METRICS=('TAREFAS','ATIVIDADES_SEQ','ATIVIDADES_PAR','TEMPO_SEQ','TEMPO_PAR','SPEEDUP','REDUCAO_PERCENTUAL')


def activity_oracle(factor):
    state=123456789
    expected=[]
    for activity in range(160):
        state=(state*1103515245+12345)&0x7fffffff
        iterations=math.floor((.05+.1*(state/2147483647))*1500000*factor)
        expected.append([activity,activity//4+1,activity%4+1,iterations,iterations*(iterations-1)//2])
    return expected


def mandelbrot_oracle(width=50,height=20,maximum=100):
    values=[]; lines=[]; palette=' .:-=+#%@'
    for y in range(height):
        row=[]; line=''; cy=(y/height)*2.4-1.2
        for x in range(width):
            cx=(x/width)*3-2; zx=zy=0.; iteration=0
            while zx*zx+zy*zy<=4 and iteration<maximum:
                temporary=zx*zx-zy*zy+cx
                zy=2*zx*zy+cy; zx=temporary; iteration+=1
            row.append(iteration)
            line+=palette[int((iteration/maximum)*(len(palette)-1))]
        values.append(row); lines.append(line)
    return values,lines


def svg_checks(path,depth=4,side=300):
    root=ET.parse(path).getroot()
    assert root.tag=='{http://www.w3.org/2000/svg}svg'
    assert list(map(float,root.attrib['viewBox'].split()))==[0,0,side,side]
    rectangles=list(root)
    background=[r for r in rectangles if r.attrib.get('fill')=='navy']
    holes=[r for r in rectangles if r.attrib.get('fill')=='white']
    assert len(background)==1 and len(rectangles)==len(holes)+1
    assert len(holes)==(8**depth-1)//7
    actual=[]
    for rectangle in holes:
        x,y,w,h=(float(rectangle.attrib[k]) for k in ('x','y','width','height'))
        assert w>0 and math.isclose(w,h) and x>=0 and y>=0
        assert x+w<=side+1e-8 and y+h<=side+1e-8
        actual.append((x,y,w,h))
    # Oraculo geometrico independente: lista das celulas centrais por nivel.
    regions=[(0.,0.,float(side))]; expected=[]
    for _ in range(depth):
        children=[]
        for x,y,length in regions:
            third=length/3; expected.append((x+third,y+third,third,third))
            for row in range(3):
                for column in range(3):
                    if (row,column)!=(1,1): children.append((x+column*third,y+row*third,third))
        regions=children
    key=lambda r: tuple(round(n,8) for n in r)
    assert sorted(map(key,actual))==sorted(map(key,expected))
    return {'path':str(path),'holes':len(holes),'depth':depth,'side':side,
            'bytes':Path(path).stat().st_size,'sha256':hashlib.sha256(Path(path).read_bytes()).hexdigest()}


def validate(number,stdout,factor=1):
    records={'SEQ':[],'PAR':[]}
    for line in stdout.splitlines():
        if line.startswith('ATIVIDADE '):
            fields=line.split()
            assert len(fields)==8 and fields[1] in records,line
            row=list(map(float,fields[2:]))
            assert all(math.isfinite(v) and v==int(v) for v in row)
            records[fields[1]].append(list(map(int,row)))
    expected=activity_oracle(factor)
    for mode,rows in records.items():
        assert len(rows)==160 and len({row[0] for row in rows})==160,mode
        assert {row[0] for row in rows}==set(range(160))
        for row in rows:
            assert row[:3]+row[4:]==expected[row[0]],row
            assert row[3]==(0 if mode=='SEQ' else row[0]//40),row
    assert {i:sum(r[3]==i for r in records['PAR']) for i in range(4)}=={i:40 for i in range(4)}
    metrics={key:float(re.search(r'^'+key+r' ([^\n]+)$',stdout,re.M)[1]) for key in METRICS}
    assert metrics['TAREFAS']==number-4
    assert metrics['ATIVIDADES_SEQ']==metrics['ATIVIDADES_PAR']==160
    assert metrics['TEMPO_SEQ']>0 and metrics['TEMPO_PAR']>0
    assert all(math.isfinite(v) for v in metrics.values())
    assert math.isclose(metrics['SPEEDUP'],metrics['TEMPO_SEQ']/metrics['TEMPO_PAR'],rel_tol=1e-12)
    assert math.isclose(metrics['REDUCAO_PERCENTUAL'],(1-metrics['TEMPO_PAR']/metrics['TEMPO_SEQ'])*100,abs_tol=1e-9)
    result={'metrics':metrics,'activities':160,'roles':4}
    if number>=9:
        lines=stdout.split('MANDELBROT_BEGIN\n',1)[1].split('\nMANDELBROT_END',1)[0].split('\n')
        assert len(lines)==20 and all(len(line)==50 for line in lines)
        assert lines==mandelbrot_oracle()[1]
        result['mandelbrot_sha256']=hashlib.sha256('\n'.join(lines).encode()).hexdigest()
    if number==10:
        paths=[Path(line[len('ARQUIVO: '):]) for line in stdout.splitlines() if line.startswith('ARQUIVO: ')]
        assert len(paths)==2 and paths[0]!=paths[1]
        result['svg']=[svg_checks(path) for path in paths]
        assert paths[0].read_bytes()==paths[1].read_bytes()
    assert 'STATUS APROVADO' in stdout
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report',type=Path,default=Path('output/validacoes/validacao-8910.json'))
    parser.add_argument('--output',type=Path,default=Path('output/validation-8910'))
    parser.add_argument('--factor',type=float,default=1)
    args=parser.parse_args()
    report={'timestamp_utc':datetime.now(timezone.utc).isoformat(), 'platform':platform.platform(),
            'python':sys.version, 'compiler':pipeline.compiler_path(), 'factor':args.factor,
            'warmup':False, 'cases':[]}
    version=subprocess.run([pipeline.compiler_path(),'--version'],capture_output=True,text=True,
                           env=pipeline.runtime_environment(),timeout=10)
    report['compiler_version']=version.stdout
    for number,source in SOURCES.items():
        directory=(ROOT / args.output).resolve()/f'teste{number}'
        record=pipeline.build(source,directory)
        record['test']=number
        if record['phases']['native_compilation']==pipeline.PASS:
            try:
                result=pipeline.run(record,env={'MINIPAR_WORK_FACTOR':str(args.factor),'MINIPAR_REMOTE':'0',
                    'MINIPAR_TRACE':str(directory/'trace.tsv')})
                assert result.returncode==0,result.stderr
                record['verified']=validate(number,result.stdout,args.factor)
                record['phases']['results']=pipeline.PASS
            except Exception as error:
                phase='results' if record['phases']['execution']==pipeline.PASS else 'execution'
                record['phases'][phase]=pipeline.FAIL; record['error']=str(error)
        record['final']=pipeline.PASS if set(record['phases'].values())=={pipeline.PASS} else pipeline.FAIL
        report['cases'].append(record); pipeline.save(ROOT / args.report,report)
        print(number,record['final'],record.get('error',''),flush=True)
    return int(any(c['final']!=pipeline.PASS for c in report['cases']))


if __name__=='__main__': sys.exit(main())
