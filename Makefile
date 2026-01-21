.PHONY: install dev test lint format build clean docker-build docker-run run analyze write help

# Load .env file if it exists
ENV_FILE := $(wildcard .env)
UV_RUN := uv run $(if $(ENV_FILE),--env-file .env,)

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

# Setup targets
setup:  ## Initial setup - create venv, install deps, copy .env
	uv venv
	uv sync --all-extras
	uv pip install -e .
	@if [ ! -f .env ]; then cp .env.example .env && echo "Created .env from .env.example - please add your API key"; fi

install:  ## Install dependencies with uv
	uv sync --all-extras
	uv pip install -e .

dev:  ## Install in editable mode (required for local changes)
	uv pip install -e .

lock:  ## Update lockfile
	uv lock

# Run targets (with .env support)
run:  ## Run critic CLI (pass ARGS, e.g., make run ARGS="analyze -n 10")
	$(UV_RUN) critic $(ARGS)

analyze:  ## Run analyze on current repo (use N=5 for count)
	$(UV_RUN) critic analyze -n $(or $(N),20)

analyze-url:  ## Analyze remote repo (use URL=<url> N=10)
	$(UV_RUN) critic analyze --url $(URL) -n $(or $(N),20)

write:  ## Run write mode for staged changes
	$(UV_RUN) critic write

config:  ## Show current config
	$(UV_RUN) critic config

version:  ## Show version
	$(UV_RUN) critic version

# Development targets
test:  ## Run tests
	$(UV_RUN) pytest tests/ -v

test-cov:  ## Run tests with coverage
	$(UV_RUN) pytest tests/ -v --cov=commit_critic --cov-report=html

lint:  ## Run linting (flat layout - check current dir)
	$(UV_RUN) ruff check .
	$(UV_RUN) mypy . --exclude docs

format:  ## Format code
	$(UV_RUN) ruff format .
	$(UV_RUN) ruff check --fix .

typecheck:  ## Run type checking only
	$(UV_RUN) mypy . --exclude docs

build:  ## Build package
	uv build

clean:  ## Clean build artifacts
	rm -rf build/ dist/ *.egg-info/ .pytest_cache/ .mypy_cache/ .ruff_cache/ htmlcov/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

# Docker targets
docker-build:  ## Build Docker image
	docker build -t commit-critic:latest .

docker-run:  ## Run in Docker (pass ARGS for commands)
	docker run --rm -it \
		--env-file .env \
		-v $(PWD):/workspace:ro \
		commit-critic:latest $(ARGS)

docker-analyze:  ## Analyze current repo in Docker
	docker run --rm -it \
		--env-file .env \
		-v $(PWD):/workspace:ro \
		-w /workspace \
		commit-critic:latest analyze

# Release targets
release-patch:  ## Bump patch version and tag
	@echo "Bumping patch version..."
	@NEW_VERSION=$$(python -c "v='$(shell grep 'version' pyproject.toml | head -1 | cut -d'\"' -f2)'; parts=v.split('.'); parts[2]=str(int(parts[2])+1); print('.'.join(parts))") && \
	sed -i '' "s/version = \".*\"/version = \"$$NEW_VERSION\"/" pyproject.toml && \
	git add pyproject.toml && \
	git commit -m "chore: bump version to $$NEW_VERSION" && \
	git tag "v$$NEW_VERSION"

release-minor:  ## Bump minor version and tag
	@echo "Bumping minor version..."
	@NEW_VERSION=$$(python -c "v='$(shell grep 'version' pyproject.toml | head -1 | cut -d'\"' -f2)'; parts=v.split('.'); parts[1]=str(int(parts[1])+1); parts[2]='0'; print('.'.join(parts))") && \
	sed -i '' "s/version = \".*\"/version = \"$$NEW_VERSION\"/" pyproject.toml && \
	git add pyproject.toml && \
	git commit -m "chore: bump version to $$NEW_VERSION" && \
	git tag "v$$NEW_VERSION"
