"""Compila/executa Testes 8–10 pela nova API e confere resultados reais."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app import app
from tools.validate_parallel import validate


def main():
    client = app.test_client()
    cases = []
    report_path = ROOT / 'output/validacoes/web-educacional-8910.json'
    report_path.parent.mkdir(parents=True, exist_ok=True)
    for number in (8, 9, 10):
        source = next((ROOT / 'tests').glob(f'teste{number}_*.minipar'))
        code = source.read_text(encoding='utf-8')
        analysis = client.post('/api/educacional/analyze', json={'code': code, 'stage': 'tac'})
        assert analysis.status_code == 200 and analysis.get_json()['success'], analysis.get_json()
        built = client.post('/api/educacional/compile', json={'code': code})
        payload = built.get_json()
        assert built.status_code == 200 and payload['success'], payload
        ran = client.post(f"/api/educacional/jobs/{payload['job_id']}/run", json={'stdin': ''})
        result = ran.get_json()
        assert ran.status_code == 200 and result['success'], result
        execution = result['execution']
        verified = validate(number, execution['stdout'])
        downloads = {}
        for artifact in result['artifacts']:
            response = client.get(artifact['url'])
            assert response.status_code == 200, artifact
            downloads[artifact['name']] = {'url': artifact['url'], 'bytes': len(response.data),
                                           'sha256': hashlib.sha256(response.data).hexdigest()}
        record = {'test': number, 'source': source.relative_to(ROOT).as_posix(),
                  'job_id': payload['job_id'], 'run_id': result['run_id'],
                  'analysis_tac_lines': len(analysis.get_json()['tac'].splitlines()),
                  'compilation_returncode': payload['compilation']['returncode'],
                  'execution_returncode': execution['returncode'],
                  'stdout_sha256': hashlib.sha256(execution['stdout'].encode()).hexdigest(),
                  'stdout_truncated': execution['stdout_truncated'],
                  'stderr': execution['stderr'], 'verified': verified, 'downloads': downloads}
        cases.append(record)
        report_path.write_text(json.dumps({'cases': cases}, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'Teste {number}: analisado, compilado e executado; resultado conferido', flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
