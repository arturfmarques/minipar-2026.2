from pathlib import Path
import pytest
from app import app

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.native
@pytest.mark.parametrize(('code', 'filename', 'expected_success'), [
    ('seq { print(42); }', 'pytest_api_ok.minipar', True),
    # Fonte válida com conversão inválida apenas em runtime: exige erro real do binário.
    ('print(to_number(input()));', 'pytest_api_nonzero.minipar', False),
])
def test_existing_web_reports_real_execution(monkeypatch, code, filename, expected_success):
    monkeypatch.chdir(ROOT)
    client = app.test_client()
    assert client.get('/').status_code == 200
    result = client.post('/api/compile', json={'code': code, 'filename': filename, 'inputs': ['invalid-number']})
    assert result.status_code == 200
    payload = result.get_json()
    assert payload['success'] is expected_success
    assert payload['cpp'] and payload['tac']
    if expected_success:
        assert '\n42\n' in payload['stdout']
    else:
        assert 'Binario encerrou com codigo 1' in payload['stderr']
        assert '[ERRO RUNTIME]' in payload['stderr']
