# cursor-session-tracer — developer tasks
# Pinned to Python 3.12 to match the reference environment.
# Override on macOS if python3.12 isn't on PATH, e.g.:
#   make setup PYTHON=/Library/Frameworks/Python.framework/Versions/3.12/bin/python3

PYTHON ?= python3.12
VENV   := .venv
BIN    := $(VENV)/bin

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

$(BIN)/python: ## Create the virtualenv
	$(PYTHON) -m venv $(VENV)
	$(BIN)/pip install --upgrade pip

.PHONY: setup
setup: $(BIN)/python ## Create venv (Python 3.12) and install dependencies
	$(BIN)/pip install -r requirements.txt
	@echo "\nSetup complete. Activate with:  source $(VENV)/bin/activate"

.PHONY: test
test: ## Run the test suite
	$(BIN)/python -m pytest tests/ -q

.PHONY: server
server: ## Start the MCP + FastAPI server on http://127.0.0.1:8080
	$(BIN)/uvicorn src.app:app --host 127.0.0.1 --port 8080 --reload

.PHONY: audit
audit: ## Audit a trace against its ADR — make audit SESSION=YYYYMMDD/<id>
	@test -n "$(SESSION)" || (echo "usage: make audit SESSION=YYYYMMDD/<session_id>" && exit 1)
	$(BIN)/python audit_trace.py --session $(SESSION)

.PHONY: clean
clean: ## Remove venv and caches
	rm -rf $(VENV) .pytest_cache **/__pycache__ tests/__pycache__ src/__pycache__
