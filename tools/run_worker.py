"""Inicia o modo trabalhador de um executável MiniPar previamente compilado."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'src'))
from toolchain import runtime_environment


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('executable',type=Path)
    parser.add_argument('--host',default='127.0.0.1')
    parser.add_argument('--port',type=int,default=7000)
    parser.add_argument('--workers',type=int,default=8)
    parser.add_argument('--max-requests',type=int,default=0)
    args=parser.parse_args()
    command=[str(args.executable.resolve()),'--worker','--host',args.host,'--port',str(args.port),
             '--workers',str(args.workers),'--max-requests',str(args.max_requests)]
    return subprocess.run(command,env=runtime_environment()).returncode


if __name__=='__main__':
    sys.exit(main())
