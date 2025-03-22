#!make

.PHONY: help

.DEFAULT_GOAL := help

help: ## show help message
	@awk 'BEGIN {FS = ":.*##"; printf "\nUsage:\n  make \033[36m\033[0m\n"} /^[$$()% 0-9a-zA-Z_-]+:.*?##/ { printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST)


# Function to export environment variables from a file
define export_env
	@echo "--- Exporting: $(1)"
	$(eval include $(1))
    $(eval export)
endef


##@ Development Environment
env: ## Export environment variables from .env file if exists
	$(call export_env,.env.default)
	$(if $(wildcard .env),$(call export_env,.env))

install_uv: ## Install uv if not found in PATH
	@if ! uv -V ; then \
        echo "uv not found, installing..."; \
        curl -LsSf https://astral.sh/uv/install.sh | sh; \
		source $(HOME)/.cargo/env ; \
    else \
        echo "uv is already installed. Skipped."; \
    fi

venv: install_uv env ## Initialize a new virtual environment in UV_PROJECT_ENVIRONMENT
	uv venv --seed

venv-activate: env ## Activate the virtual environment
	. $(UV_PROJECT_ENVIRONMENT)/bin/activate && exec $$SHELL

dev-install: requirements ## Install the package in development mode
	uv pip install -e .

template-update: ## Update the project with the latest template version
	copier update -A

##@ Dependencies Management
requirements: env ## Install all dependencies including dev, extras
	uv sync

requirements-purge: env ## Uninstall all dependencies from current environment
	uv pip freeze | cut -d "@" -f1 | xargs uv pip uninstall

# Execute uv with the variable UV_PROJECT_ENVIRONMENT defined in .env
# Example: > make uv tree -- --outdated
uv: env ## Execute uv commands with the custom environment
	uv $(filter-out $@, $(MAKECMDGOALS))


##@ Code Quality
lint: env ## Run the linters
	uv run ruff format --check .
	uv run ruff check .

lint-fix: env ## Apply linting and formatting fixes to codebase - use with caution
	uv run ruff format .
	uv run ruff check --fix .

type-check: env ## Run the static type checker
	uv run mypy src

lint-ci: lint type-check ## Run the linters and static type checker for CI

##@ Testing
test: env ## Run the tests in local environment
	uv run pytest tests

test-lock: env ## Verify that uv.lock is up-to-date
	uv lock --check

test-ci: test test-lock ## Specific test command for GitHub CI environment

check-all: lint-ci test ## Run all checks and tests


##@ Build and Publishing
executable: env ## Build the executable with PyInstaller with existing main.spec file
	uv run pyinstaller main.spec

build: env ## Build the package - for dev purposes
	uv build

publish: env build ## Publish the package to devpi
	@uv publish

current_version: ## Get current package version
	$(eval version := $(shell uv run python -c "from src.battery_notifier import __version__; print(__version__)"))
	@echo "Current version is: $(version)"

bump: current_version ## Commit version bump changes for production
	git add src/battery_notifier/__about__.py CHANGELOG.md
	git diff --quiet && git diff --staged --quiet || git commit -m "Release $(version)"
	git diff --quiet origin/HEAD || git push origin HEAD

release: bump ## Release a new version via Github actions
	git tag -a $(version) -m "Release $(version)"
	git push origin $(version)

gh-release: bump ## Release a new version using gh CLI
	gh release create $(version) --generate-notes


%:
	@true
