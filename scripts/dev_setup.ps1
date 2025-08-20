python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -U pip pre-commit
pre-commit install
npm install --prefix services/integration-hub
npm install --prefix services/salesforce-mock
