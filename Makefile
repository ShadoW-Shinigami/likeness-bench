.PHONY: help env install dev build serve self-check test lint clean web-install web-build

CONDA_RUN := /opt/anaconda3/bin/conda run -n eval --no-capture-output

help:
	@echo "Setup:"
	@echo "  make install        install Python deps into conda env 'eval'"
	@echo "  make web-install    install web deps (npm)"
	@echo "  make build          build React frontend"
	@echo "  make serve          run FastAPI :8000 (API + React UI)"
	@echo ""
	@echo "Workflow:"
	@echo "  make refresh        run any unevaluated models + rebuild showcase"
	@echo "  make eval-all       run all configured models against default benchmark"
	@echo "  make showcase       rebuild showcase.html only"
	@echo ""
	@echo "Other:"
	@echo "  make self-check     run mock provider over tiny benchmark"
	@echo "  make test           run pytest"
	@echo "  make lint           ruff"

install:
	$(CONDA_RUN) pip install -e ".[providers,dev]"

web-install:
	cd web && npm install

build:
	cd web && npm run build

serve:
	$(CONDA_RUN) bench serve

dev: build serve

refresh:
	$(CONDA_RUN) bench refresh

eval-all:
	$(CONDA_RUN) bench eval-all

showcase:
	$(CONDA_RUN) bench refresh-showcase

self-check:
	$(CONDA_RUN) bench self-check

test:
	$(CONDA_RUN) pytest -v

lint:
	$(CONDA_RUN) ruff check .

clean:
	rm -rf web/dist web/node_modules build dist *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} +
