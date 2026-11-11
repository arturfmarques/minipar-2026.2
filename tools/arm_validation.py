"""Monta ARM com Zig/LLVM e executa o ELF no Unicorn Cortex-A9.

Nao recebe expressoes nem gera Assembly: somente valida o arquivo do MiniPar.
"""
from pathlib import Path
import json
import os
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def arm_environment():
    env=os.environ.copy()
    for variable,folder in [('ZIG_GLOBAL_CACHE_DIR','global'),('ZIG_LOCAL_CACHE_DIR','local')]:
        path=ROOT/'output/zig-cache'/folder
        path.mkdir(parents=True,exist_ok=True)
        env[variable]=str(path)
    return env


def assemble(source,elf):
    import ziglang
    executable=Path(ziglang.__file__).with_name('zig.exe' if os.name=='nt' else 'zig')
    command=[str(executable),'cc','-target','arm-freestanding-eabi','-mcpu=cortex_a9',
             '-x','assembler','-nostdlib','-Wl,-e,_start',str(source),'-o',str(elf)]
    result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace',
                          timeout=120,env=arm_environment())
    return {'command':command,'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr}


def emulate(elf_path,instruction_limit=1000000):
    from elftools.elf.elffile import ELFFile
    from unicorn import Uc,UC_ARCH_ARM,UC_MODE_ARM,UC_MODE_LITTLE_ENDIAN,UC_HOOK_CODE
    from unicorn.arm_const import UC_ARM_REG_R0,UC_ARM_REG_R12,UC_ARM_REG_SP,UC_CPU_ARM_CORTEX_A9
    with Path(elf_path).open('rb') as stream:
        elf=ELFFile(stream)
        if elf['e_machine']!='EM_ARM' or not elf.little_endian: raise ValueError('ELF ARM little-endian exigido')
        segments=[(int(s['p_vaddr']),int(s['p_memsz']),s.data()) for s in elf.iter_segments() if s['p_type']=='PT_LOAD' and s['p_memsz']]
        entry=int(elf['e_entry'])
        table=elf.get_section_by_name('.symtab')
        symbols={s.name:int(s['st_value']) for s in table.iter_symbols()}
    stop=symbols['__expr_done']; stack_top=symbols['__expr_stack_top']; stack_base=symbols['__expr_stack']
    uc=Uc(UC_ARCH_ARM,UC_MODE_ARM|UC_MODE_LITTLE_ENDIAN)
    uc.ctl_set_cpu_model(UC_CPU_ARM_CORTEX_A9)
    pages=set()
    for address,size,data in segments:
        for page in range(address&~4095,(address+size+4095)&~4095,4096): pages.add(page)
    for page in sorted(pages): uc.mem_map(page,4096)
    for address,size,data in segments:
        if data: uc.mem_write(address,data)
    state={'instructions':0,'minimum_sp':stack_top,'stopped_at_done':False,'aligned':True}
    def step(engine,address,size,user):
        state['instructions']+=1
        sp=int(engine.reg_read(UC_ARM_REG_SP))
        if sp:
            state['minimum_sp']=min(state['minimum_sp'],sp)
            state['aligned']=state['aligned'] and sp%8==0
        if address==stop:
            state['stopped_at_done']=True
            engine.emu_stop()
    uc.hook_add(UC_HOOK_CODE,step)
    uc.emu_start(entry,0xffffffff,count=instruction_limit)
    raw=int(uc.reg_read(UC_ARM_REG_R0)); final_sp=int(uc.reg_read(UC_ARM_REG_SP))
    result={**state,'engine':'Unicorn Cortex-A9','entry':entry,'stop_address':stop,
            'r0_unsigned':raw,'r0_signed':raw-(1<<32) if raw&(1<<31) else raw,
            'r12_status':int(uc.reg_read(UC_ARM_REG_R12)), 'stack_top':stack_top,'stack_base':stack_base,
            'final_sp':final_sp,'stack_balanced':final_sp==stack_top,
            'max_stack_bytes':stack_top-state['minimum_sp']}
    if not result['stopped_at_done']: raise RuntimeError(f'ARM nao atingiu __expr_done: {result}')
    if not result['stack_balanced'] or not result['aligned'] or state['minimum_sp']<stack_base:
        raise RuntimeError(f'Pilha ARM invalida: {result}')
    if result['r12_status']!=0: raise RuntimeError(f'ARM reportou erro: {result}')
    return result


def validate_arm(source,elf):
    record={'source':str(source),'elf':str(elf),'assembler':assemble(source,elf),'emulation':None}
    if record['assembler']['returncode']==0:
        # Isola o motor nativo e seus handlers de excecao dos hooks do pytest.
        # Crash, timeout, stderr e JSON ausente continuam erros impeditivos.
        command=[sys.executable,str(Path(__file__).resolve()),'--emulate',str(elf)]
        child=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',timeout=30)
        record['emulator_process']={'command':command,'returncode':child.returncode,'stderr':child.stderr}
        if child.returncode!=0 or child.stderr:
            raise RuntimeError(f'Emulador ARM falhou: {record["emulator_process"]}')
        record['emulation']=json.loads(child.stdout)
    return record


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--emulate',required=True,type=Path)
    args=parser.parse_args()
    print(json.dumps(emulate(args.emulate)))
