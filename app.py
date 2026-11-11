from flask import Flask, render_template, request, jsonify, send_file, abort, url_for
from pathlib import Path
import re
import subprocess
import os
import sys
import glob
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), 'src'))
from toolchain import runtime_environment
from educational_web import educational

from test_orchestrator import (
    get_spec_summary,
    finalize_test_execution,
    check_active_session_for_new_terminal,
    join_session,
    get_terminal_id,
    create_session,
    clear_session,
    set_session_phase,
    append_session_log,
    record_execution_output,
    _load_session,
    _save_session,
)

app = Flask(__name__)
app.register_blueprint(educational)

# Configuração de Diretórios
TESTS_DIR = 'tests'
OUTPUT_DIR = 'output'
TEMP_DIR = 'temp_code'

os.makedirs(TEMP_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)


def _safe_minipar_name(filename):
    """Aceita apenas nomes simples nas APIs de arquivos da IDE original."""
    return (isinstance(filename, str) and 1 <= len(filename) <= 120
            and filename.endswith('.minipar') and not filename.startswith('.')
            and not any(char in filename for char in '/\\:')
            and all(ord(char) >= 32 for char in filename))

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/tests', methods=['GET'])
def get_tests():
    # Retorna os testes ordenados alfabeticamente
    tests = [os.path.basename(f) for f in glob.glob(os.path.join(TESTS_DIR, '*.minipar'))]
    return jsonify({"tests": sorted(tests)})

@app.route('/api/get_test', methods=['POST'])
def get_test():
    filename = request.json.get('filename')
    if not _safe_minipar_name(filename):
        return jsonify({"error": "Nome de arquivo inválido"}), 400
    filepath = os.path.join(TESTS_DIR, filename)
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return jsonify({"code": f.read()})
    return jsonify({"error": "Arquivo não encontrado"}), 404


def _generated_artifact(path):
    resolved = Path(path).resolve()
    root = Path(OUTPUT_DIR).resolve()
    if not resolved.is_relative_to(root) or resolved.suffix.lower() not in ('.svg', '.arm') or not resolved.is_file():
        return None
    return resolved


@app.route('/api/artifacts/<path:filename>', methods=['GET'])
def get_artifact(filename):
    path = _generated_artifact(Path(OUTPUT_DIR) / filename)
    if path is None: abort(404)
    is_arm = path.suffix.lower() == '.arm'
    response = send_file(path, mimetype='text/plain' if is_arm else 'image/svg+xml', as_attachment=is_arm)
    response.headers['Content-Security-Policy'] = "sandbox; default-src 'none'; style-src 'unsafe-inline'"
    return response


def _collect_artifacts(output):
    artifacts = []
    for filename in re.findall(r'^ARQUIVO: (.+)$', output, re.M):
        path = _generated_artifact(filename)
        if path:
            name = path.relative_to(Path(OUTPUT_DIR).resolve()).as_posix()
            artifacts.append({'name': name, 'url': url_for('get_artifact', filename=name)})
    return artifacts

@app.route('/api/test_spec', methods=['POST'])
def get_test_spec_api():
    """Requisitos detectados automaticamente pelo program_analyzer."""
    filename = request.json.get('filename')
    if not _safe_minipar_name(filename):
        return jsonify({"error": "Nome de arquivo inválido"}), 400
    spec = get_spec_summary(filename)
    if spec:
        return jsonify(spec)
    return jsonify({"requires_input": False, "multi_computer": None})


@app.route('/api/session', methods=['GET'])
def get_session():
    action, session = check_active_session_for_new_terminal()
    if session:
        return jsonify({
            "active": session.get("status") not in ("completed", "cancelled"),
            "session": session,
            "terminal_id": get_terminal_id(),
            "needs_choice": action is not None,
        })
    return jsonify({"active": False, "terminal_id": get_terminal_id()})


@app.route('/api/session/join', methods=['POST'])
def session_join():
    _, session = check_active_session_for_new_terminal()
    if session:
        join_session(session)
        return jsonify({"success": True, "session": session})
    return jsonify({"success": False, "error": "Nenhuma sessão ativa"}), 404


@app.route('/api/session/create', methods=['POST'])
def session_create():
    filename = request.json.get('filename')
    if not _safe_minipar_name(filename):
        return jsonify({"success": False, "error": "Nome de arquivo inválido"}), 400
    path = os.path.join(TESTS_DIR, filename)
    if not os.path.exists(path):
        return jsonify({"success": False, "error": "Arquivo não encontrado"}), 404
    from program_analyzer import get_program_spec
    spec = get_program_spec(path)
    if not spec.get('multi_computer'):
        return jsonify({"success": False, "error": "Programa não requer multi-terminal"}), 400
    session = create_session(path, spec)
    return jsonify({"success": True, "session": session})


@app.route('/api/session/ready', methods=['POST'])
def session_ready():
    session = _load_session()
    if session:
        session["status"] = "running"
        _save_session(session)
        return jsonify({"success": True})
    return jsonify({"success": False}), 404


@app.route('/api/session/clear', methods=['POST'])
def session_clear():
    clear_session()
    return jsonify({"success": True})


@app.route('/api/compile', methods=['POST'])
def compile_code():
    data = request.json
    if not isinstance(data, dict):
        return jsonify({"success": False, "error": "Envie um objeto JSON"}), 400
    code = data.get('code')
    filename = data.get('filename', 'ide_temp.minipar')
    if not isinstance(code, str) or len(code.encode('utf-8')) > 200_000 or not _safe_minipar_name(filename):
        return jsonify({"success": False, "error": "Código ou nome de arquivo inválido"}), 400
    user_inputs = data.get('inputs', [])
    tac_only = data.get('tac_only') is True
    
    # Salva o código recebido da IDE em um arquivo temporário
    file_path = os.path.join(TEMP_DIR, filename)
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(code)
        
    base_name = filename.replace('.minipar', '')
    stdin_lines = user_inputs  # valores coletados pela IDE para input() no .minipar
    
    try:
        set_session_phase("compiling", "Compilando código MiniPar...", percent=60)
        append_session_log("Compilação iniciada via IDE Web.")
        # ==========================================
        # 1. FASE DE COMPILAÇÃO (Gera TAC e C++)
        # ==========================================
        process = subprocess.run(
            [sys.executable, 'main.py', file_path] + (['--tac-only'] if tac_only else []),
            capture_output=True, 
            text=True, 
            timeout=125
        )
        
        # Junta logs do sistema
        full_output = process.stdout
        if process.stderr:
            full_output += "\n" + process.stderr
            
        success = process.returncode == 0

        # ==========================================
        # 2. FASE DE EXECUÇÃO (Roda o Binário C++)
        # ==========================================
        if success and not tac_only:
            set_session_phase("compiling", "Compilação concluída.", percent=80)
            append_session_log("Compilação concluída — executando binário.")
            exe_ext = ".exe" if sys.platform == "win32" else ""
            exe_path = os.path.join(OUTPUT_DIR, f"{base_name}{exe_ext}")
            
            if os.path.exists(exe_path):
                full_output += f"\n--- Executando {base_name} ---\n"
                set_session_phase("executing", f"Executando {base_name}...", percent=90)
                try:
                    stdin_data = None
                    if stdin_lines:
                        stdin_data = "\n".join(stdin_lines) + "\n"
                    exe_proc = subprocess.run(
                        [os.path.abspath(exe_path)], 
                        input=stdin_data,
                        capture_output=True, 
                        text=True, 
                        timeout=30,
                        env=runtime_environment(),
                    )
                    full_output += exe_proc.stdout
                    success = exe_proc.returncode == 0
                    if not success:
                        full_output += f"\n[ERRO] Binario encerrou com codigo {exe_proc.returncode}.\n"
                    if exe_proc.stderr:
                        full_output += "\n[ERRO NA EXECUÇÃO]:\n" + exe_proc.stderr
                    record_execution_output(exe_proc.stdout or "")
                except subprocess.TimeoutExpired:
                    full_output += "\n[ERRO] Tempo limite de execução excedido (O programa entrou em loop infinito ou aguarda entrada de dados do usuário?)."
                    success = False
                except Exception as e:
                    full_output += f"\n[ERRO] Falha ao executar binário: {e}"
                    success = False
                
                full_output += "\n" + "-" * 40

                if filename.endswith('.minipar'):
                    test_source = os.path.join(TESTS_DIR, filename)
                    if os.path.exists(test_source):
                        finalize_test_execution(test_source, full_output)
            else:
                success = False
                full_output += f"\n[ERRO] Executavel nao encontrado: {exe_path}\n"
        
        # ==========================================
        # 3. COLETA DOS ARQUIVOS GERADOS
        # ==========================================
        cpp_file = os.path.join(OUTPUT_DIR, f"{base_name}.cpp")
        tac_file = os.path.join(OUTPUT_DIR, f"{base_name}.tac")
        
        cpp_code = ""
        tac_code = ""
        
        if not tac_only and '[CODEGEN] Compilando via' in process.stdout and os.path.exists(cpp_file):
            with open(cpp_file, 'r', encoding='utf-8') as f:
                cpp_code = f.read()
                
        if '[TAC] Arquivo gerado:' in process.stdout and os.path.exists(tac_file):
             with open(tac_file, 'r', encoding='utf-8') as f:
                tac_code = f.read()
                
        # Retorna o resultado. Se der erro, colocamos o log completo em stderr para o JS puxar
        return jsonify({
            "stdout": full_output if success else "",
            "stderr": full_output if not success else "",
            "cpp": cpp_code,
            "tac": tac_code,
            "artifacts": _collect_artifacts(full_output) if success else [],
            "success": success
        })
        
    except subprocess.TimeoutExpired:
        return jsonify({"error": "Tempo limite do compilador excedido.", "success": False}), 500
    except Exception as e:
        return jsonify({"error": str(e), "success": False}), 500

if __name__ == '__main__':
    # Roda a IDE silenciosamente
    app.run(host='127.0.0.1', debug=False, port=5000)
