"""Segunda Web: apresentação das fases do compilador MiniPar existente."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import subprocess
import sys
import threading
import time

from flask import Blueprint, abort, jsonify, render_template, request, send_file, url_for

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'src'))
from educational_pipeline import STAGES, analyze_source
from toolchain import ToolchainError, compile_command, compiler_path, executable_suffix, runtime_environment

educational = Blueprint('educational', __name__)
WORKSPACE = ROOT / 'output' / 'educacional'
CODE_LIMIT = 200_000
INPUT_LIMIT = 16_384
LOG_LIMIT = 65_536
FILE_LIMIT = 20_000_000
JOB_TTL = 24 * 60 * 60
COMPILE_TIMEOUT = 120
EXEC_TIMEOUT = 30
HEX_ID = re.compile(r'[a-f0-9]{32}\Z')


def _problem(message, status=400):
    return jsonify({'success': False, 'error': message}), status


def _body():
    data = request.get_json(silent=True)
    if not isinstance(data, dict): raise ValueError('Envie um objeto JSON.')
    return data


def _code(data):
    code = data.get('code')
    if not isinstance(code, str): raise ValueError('O campo code deve ser texto MiniPar.')
    if len(code.encode('utf-8')) > CODE_LIMIT: raise ValueError('Código excede 200 kB.')
    return code


def _examples():
    examples = {}
    for path in (ROOT / 'tests').glob('teste[0-9]*.minipar'):
        match = re.match(r'teste(\d+)_', path.name)
        if match and 1 <= int(match.group(1)) <= 11:
            examples[path.name] = {'key': path.name, 'name': f'Teste {int(match.group(1))} · {path.stem.split("_", 1)[1].replace("_", " ")}',
                                   'group': 'Programas 1–11', 'order': int(match.group(1)), 'path': path}
    for path in sorted((ROOT / 'examples' / 'didaticos').glob('*.minipar')):
        examples[path.name] = {'key': path.name, 'name': path.stem.replace('_', ' ').capitalize(),
                               'group': 'Exemplos didáticos', 'order': 100, 'path': path}
    for path in sorted((ROOT / 'examples').glob('fork_join_*.minipar')):
        examples[path.name] = {'key': path.name, 'name': path.stem.replace('_', ' ').capitalize(),
                               'group': 'Exemplos didáticos', 'order': 101, 'path': path}
    return examples


def _job(job_id):
    if not HEX_ID.fullmatch(job_id): abort(404)
    path = WORKSPACE / job_id
    if path.is_symlink() or not path.is_dir() or not (path / 'job.json').is_file(): abort(404)
    if not path.resolve().is_relative_to(WORKSPACE.resolve()): abort(404)
    return path


def _cleanup():
    """Remove apenas diretórios antigos criados por esta interface."""
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    cutoff = time.time() - JOB_TTL
    for child in WORKSPACE.iterdir():
        if (HEX_ID.fullmatch(child.name) and child.is_dir() and not child.is_symlink()
                and child.resolve().is_relative_to(WORKSPACE.resolve())
                and (child / 'job.json').is_file() and child.stat().st_mtime < cutoff):
            shutil.rmtree(child)


def _bounded_process(command, *, cwd, env, timeout, stdin=b''):
    """Drena pipes mesmo após atingir o limite exibido; timeout encerra o grupo."""
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
    process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               creationflags=flags, start_new_session=os.name != 'nt')
    collected = {}

    def drain(name, stream):
        chunks = bytearray()
        total = 0
        while part := stream.read(8192):
            total += len(part)
            if len(chunks) < LOG_LIMIT:
                chunks.extend(part[:LOG_LIMIT - len(chunks)])
        # subprocess.run(text=True) da IDE antiga também entrega linhas normalizadas.
        collected[name] = (chunks.decode('utf-8', errors='replace').replace('\r\n', '\n'),
                           total > LOG_LIMIT)

    def feed():
        try:
            if stdin: process.stdin.write(stdin)
            process.stdin.close()
        except (BrokenPipeError, OSError, ValueError):
            pass

    readers = [threading.Thread(target=drain, args=(name, stream), daemon=True)
               for name, stream in (('stdout', process.stdout), ('stderr', process.stderr))]
    for reader in readers: reader.start()
    writer = threading.Thread(target=feed, daemon=True)
    writer.start()
    timed_out = False
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        if os.name == 'nt':
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                           capture_output=True, timeout=5)
        else:
            os.killpg(process.pid, signal.SIGKILL)
        process.kill() if process.poll() is None else None
        process.wait(timeout=5)
    for reader in readers: reader.join(timeout=3)
    writer.join(timeout=3)
    return {'command': [str(item) for item in command], 'returncode': process.returncode,
            'timed_out': timed_out,
            'stdout': collected.get('stdout', ('', False))[0],
            'stderr': collected.get('stderr', ('', False))[0],
            'stdout_truncated': collected.get('stdout', ('', False))[1],
            'stderr_truncated': collected.get('stderr', ('', False))[1]}


def _url(job_id, name):
    return url_for('educational.download', job_id=job_id, filename=name)


@educational.get('/educacional')
def page():
    return render_template('educacional.html')


@educational.get('/api/educacional/examples')
def examples():
    return jsonify({'examples': [{key: item[key] for key in ('key', 'name', 'group', 'order')}
                                for item in sorted(_examples().values(), key=lambda e: (e['order'], e['name']))]})


@educational.get('/api/educacional/examples/<key>')
def example(key):
    item = _examples().get(key)
    if item is None: abort(404)
    return jsonify({'name': item['name'], 'code': item['path'].read_text(encoding='utf-8')})


@educational.post('/api/educacional/analyze')
def analyze():
    try:
        data = _body()
        code = _code(data)
        stage = data.get('stage')
        if stage not in STAGES: raise ValueError('Etapa desconhecida.')
        return jsonify(analyze_source(code, stage))
    except ValueError as error:
        return _problem(str(error))
    except Exception:
        return _problem('Falha interna durante a análise.', 500)


@educational.post('/api/educacional/compile')
def compile_program():
    try:
        data = _body()
        code = _code(data)
        analyzed = analyze_source(code, 'cpp')
        if not analyzed['success']:
            return jsonify({'success': False, 'analysis': analyzed, 'error': 'A análise impediu a compilação.'}), 422
        _cleanup()
        job_id = secrets.token_hex(16)
        folder = WORKSPACE / job_id
        folder.mkdir(mode=0o700)
        (folder / 'job.json').write_text(json.dumps({'compiled': False}), encoding='utf-8')
        (folder / 'program.minipar').write_text(code, encoding='utf-8')
        (folder / 'program.tac').write_text(analyzed['tac'], encoding='utf-8')
        (folder / 'program.cpp').write_text(analyzed['cpp'], encoding='utf-8')
        executable = folder / ('program' + executable_suffix())
        command = compile_command(folder / 'program.cpp', executable, compiler_path())
        compilation = _bounded_process(command, cwd=folder, env=runtime_environment(), timeout=COMPILE_TIMEOUT)
        success = compilation['returncode'] == 0 and not compilation['timed_out'] and executable.is_file()
        (folder / 'job.json').write_text(json.dumps({'compiled': success,
            'remote_forks': analyzed['remote_forks']}), encoding='utf-8')
        return jsonify({'success': success, 'job_id': job_id, 'compilation': compilation,
            'phases': {**analyzed['phases'], 'compile': 'aprovada' if success else 'reprovada'},
            'remote_forks': analyzed['remote_forks'],
            'filename': executable.name if success else None,
            'downloads': {'cpp': _url(job_id, 'program.cpp'), 'tac': _url(job_id, 'program.tac'),
                          **({'executable': _url(job_id, executable.name)} if success else {})}})
    except ValueError as error:
        return _problem(str(error))
    except (ToolchainError, OSError, subprocess.SubprocessError) as error:
        return _problem(f'Falha na compilação nativa: {error}', 500)
    except Exception:
        return _problem('Falha interna durante a compilação.', 500)


@educational.post('/api/educacional/jobs/<job_id>/run')
def run_program(job_id):
    folder = _job(job_id)
    try:
        metadata = json.loads((folder / 'job.json').read_text(encoding='utf-8'))
        executable = folder / ('program' + executable_suffix())
        if not metadata.get('compiled') or not executable.is_file():
            return _problem('Este trabalho não possui binário compilado.', 409)
        data = _body()
        stdin = data.get('stdin', '')
        if not isinstance(stdin, str) or len(stdin.encode('utf-8')) > INPUT_LIMIT:
            raise ValueError('stdin deve ser texto com até 16 kB.')
        run_id = secrets.token_hex(16)
        run_folder = folder / 'runs' / run_id
        (run_folder / 'output').mkdir(parents=True)
        env = runtime_environment()
        env['MINIPAR_ARM_OUTPUT'] = str(run_folder / 'output' / 'teste11-expressao.arm')
        env['MINIPAR_OUTPUT_PREFIX'] = str(run_folder / 'output' / 'teste10')
        execution = _bounded_process([str(executable)], cwd=run_folder, env=env,
                                     timeout=EXEC_TIMEOUT, stdin=stdin.encode('utf-8'))
        success = execution['returncode'] == 0 and not execution['timed_out']
        artifacts = []
        if success:
            for path in sorted((run_folder / 'output').rglob('*')):
                if path.is_file() and path.suffix.lower() in ('.arm', '.svg') and path.stat().st_size <= FILE_LIMIT:
                    relative = path.relative_to(folder).as_posix()
                    artifacts.append({'name': path.name, 'url': _url(job_id, relative)})
        return jsonify({'success': success, 'run_id': run_id, 'execution': execution,
                        'artifacts': artifacts, 'remote_forks': metadata['remote_forks']})
    except ValueError as error:
        return _problem(str(error))
    except (OSError, subprocess.SubprocessError) as error:
        return _problem(f'Falha ao executar binário: {error}', 500)
    except Exception:
        return _problem('Falha interna durante a execução.', 500)


@educational.get('/api/educacional/jobs/<job_id>/files/<path:filename>')
def download(job_id, filename):
    folder = _job(job_id)
    relative = Path(filename)
    parts = relative.parts
    build_file = len(parts) == 1 and parts[0] in ('program.cpp', 'program.tac', 'program.exe', 'program')
    artifact = (len(parts) >= 4 and parts[0] == 'runs' and HEX_ID.fullmatch(parts[1])
                and parts[2] == 'output' and relative.suffix.lower() in ('.arm', '.svg'))
    if not (build_file or artifact): abort(404)
    file = folder / relative
    if file.is_symlink() or not file.resolve().is_relative_to(folder.resolve()) or not file.is_file(): abort(404)
    if file.stat().st_size > FILE_LIMIT: abort(413)
    if build_file and file.suffix == executable_suffix() and not json.loads((folder / 'job.json').read_text(encoding='utf-8'))['compiled']:
        abort(404)
    return send_file(file, as_attachment=True, download_name=file.name,
                     mimetype='text/plain' if file.suffix in ('.cpp', '.tac', '.arm') else None)
