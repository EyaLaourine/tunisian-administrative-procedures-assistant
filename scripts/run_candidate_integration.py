"""Run unchanged integration tests with only their webhook URL redirected.

Telegram API calls in these tests remain mocked. Retrieval tests use the local
Qdrant/Ollama services; the candidate n8n workflow uses the isolated backend.
"""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import pytest


class CandidateEndpoints:
    def pytest_collection_modifyitems(self, items):
        for item in items:
            if item.module.__name__.rsplit('.', 1)[-1] in {
                'test_integration_assistant', 'test_integration_dialogue', 'test_telegram_integration'
            }:
                for name in ('WEBHOOK', 'URL'):
                    if hasattr(item.module, name):
                        setattr(item.module, name, 'http://localhost:5679/webhook/assistant')


if __name__ == '__main__':
    raise SystemExit(pytest.main(['tests', '-m', 'integration', '-q', '--tb=short',
        '--junitxml=data/evaluation/post_audit_integration.xml'], plugins=[CandidateEndpoints()]))
