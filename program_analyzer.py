"""
Análise estática de programas MiniPar — detecta requisitos de entrada
e execução multi-terminal diretamente do código-fonte.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any, Optional


def _read_source(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def _extract_title(source: str, filename: str) -> str:
    for line in source.splitlines():
        line = line.strip()
        if line.startswith("#") and len(line) > 2:
            return line.lstrip("#").strip()
    return filename.replace(".minipar", "")


def _find_inputs(source: str) -> list[dict[str, str]]:
    """Detecta chamadas input() no código MiniPar."""
    inputs: list[dict[str, str]] = []

    # input("prompt") — cada prompt vira uma entrada identificada
    for match in re.finditer(r'input\s*\(\s*"((?:\\.|[^"\\])*)"\s*\)', source):
        prompt = match.group(1).replace("\\n", "\n").replace('\\"', '"')
        if prompt == "":
            continue  # input("") é tratado abaixo (geralmente dentro de loop)
        desc = prompt.strip() if prompt.strip() else "Entrada do teclado"
        inputs.append({"prompt": prompt, "descricao": desc})

    # input() ou input("") sem prompt: expande pelo limite do while (ex.: i < 16)
    bare_count = len(re.findall(r'input\s*\(\s*\)', source))
    empty_quoted = len(re.findall(r'input\s*\(\s*""\s*\)', source))
    empty_total = bare_count + empty_quoted

    if empty_total:
        loop_match = re.search(r'while\s*\(\s*\w+\s*<\s*(\d+)\s*\)', source)
        count = int(loop_match.group(1)) if loop_match else empty_total
        for i in range(count):
            inputs.append({"prompt": "", "descricao": f"Entrada {i + 1}"})

    return inputs


def _count_channels(source: str) -> int:
    return len(re.findall(r'\bc_channel\s*\(', source))


def analyze_program(source_path: str) -> dict[str, Any]:
    """Analisa um arquivo .minipar e retorna requisitos de execução."""
    filename = os.path.basename(source_path)
    source = _read_source(source_path)
    titulo = _extract_title(source, filename)
    inputs = _find_inputs(source)

    has_send = bool(re.search(r'\bsend\s*\(', source))
    has_receive = bool(re.search(r'\breceive\s*\(', source))
    has_par = bool(re.search(r'\bpar\s*\{', source))
    channel_count = _count_channels(source)
    # Fork/Join administra as tarefas no runtime; canais podem ser barreiras
    # internas e nao significam que usuarios devam abrir varios terminais.
    compiler_path = str(Path(__file__).resolve().parent / 'src')
    if compiler_path not in sys.path:
        sys.path.insert(0, compiler_path)
    from lexer import Lexer
    from diagnostics import CompilerError
    try:
        tokens = Lexer(source).tokenize()
        task_modes = sorted({tokens[i + 1].lexeme for i, token in enumerate(tokens[:-1])
                             if token.type.name == 'FORK'
                             and tokens[i + 1].type.name in ('LOCAL', 'REMOTE')})
    except CompilerError:
        task_modes = []  # o compilador exibe o diagnostico ao compilar

    multi_computer: Optional[dict[str, Any]] = None
    # c_channel + send/receive indica comunicação entre terminais distintos
    if channel_count > 0 and (has_send or has_receive) and not task_modes:
        count = max(channel_count, 2)  # mínimo cliente + servidor
        roles = [f"computador_{i + 1}" for i in range(count)]
        multi_computer = {
            "required": True,
            "count": count,
            "roles": roles,
            "instrucoes": (
                f"Este programa usa {channel_count} canal(is) de comunicação (c_channel). "
                f"Abra {count - 1} terminal(is) adicional(is), execute python main.py "
                f"e escolha 'Continuar teste em andamento'."
            ),
        }

    return {
        "titulo": titulo,
        "descricao": f"Arquivo: {filename}",
        "filename": filename,
        "inputs": inputs,
        "requires_input": len(inputs) > 0,
        "input_count": len(inputs),
        "multi_computer": multi_computer,
        "has_par": has_par,
        "channel_count": channel_count,
        "task_modes": task_modes,
    }


def get_program_spec(source_path: str) -> dict[str, Any]:
    """Retorna spec do programa; analisa o arquivo se existir."""
    if os.path.isfile(source_path):
        return analyze_program(source_path)
    filename = os.path.basename(source_path)
    return {
        "titulo": filename.replace(".minipar", ""),
        "descricao": "",
        "filename": filename,
        "inputs": [],
        "requires_input": False,
        "input_count": 0,
        "multi_computer": None,
        "has_par": False,
        "channel_count": 0,
        "task_modes": [],
    }
