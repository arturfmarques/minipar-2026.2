"""Seleção portátil de G++ e ambiente compartilhado por compilação/execução."""
from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import sys


class ToolchainError(RuntimeError):
    pass


def compiler_path() -> str:
    # Overrides são um executável (sem flags); não há fallback silencioso.
    override = os.environ.get("MINIPAR_CXX") or os.environ.get("CXX")
    if override:
        found = shutil.which(override)
        if not found:
            raise ToolchainError(f"Compilador configurado nao encontrado: {override}")
        return str(Path(found).resolve())
    if sys.platform == "win32":
        # Instalações MSYS2 usuais precedem o MinGW legado do PATH.
        for prefix in ("C:/msys64/ucrt64", "C:/msys64/mingw64"):
            candidate = Path(prefix) / "bin/g++.exe"
            if candidate.is_file():
                return str(candidate)
    found = shutil.which("g++")
    if found:
        return str(Path(found).resolve())
    raise ToolchainError("G++ C++20 nao encontrado. Configure MINIPAR_CXX (GCC 13+ recomendado).")


def runtime_environment(compiler: str | None = None) -> dict[str, str]:
    env = os.environ.copy()
    # No Windows os executáveis GCC podem depender de DLLs ao lado do g++.
    compiler = compiler or compiler_path()
    env["PATH"] = str(Path(compiler).parent) + os.pathsep + env.get("PATH", "")
    return env


def executable_suffix(platform: str | None = None) -> str:
    return ".exe" if (platform or sys.platform) == "win32" else ""


def compile_command(source: Path, executable: Path, compiler: str,
                    platform: str | None = None) -> list[str]:
    command = [compiler, "-std=c++20", "-O3", str(source), "-o", str(executable), "-pthread"]
    if (platform or sys.platform) == "win32":
        command.append("-lws2_32")
    return command


def compile_cpp(source: Path, executable: Path, timeout: float = 120) -> subprocess.CompletedProcess:
    compiler = compiler_path()
    command = compile_command(source, executable, compiler)
    try:
        return subprocess.run(command, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", env=runtime_environment(compiler), timeout=timeout)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ToolchainError(f"Falha ao executar compilador C++: {exc}") from exc
