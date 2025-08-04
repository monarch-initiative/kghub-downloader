# Makefile for kghub-downloader

# Variables
RUN = poetry run

# Default target
.PHONY: help
help:
	@echo "Available targets:"
	@echo "  test          - Run all tests"
	@echo "  test-unit     - Run unit tests only"
	@echo "  test-integration - Run integration tests only"
	@echo "  lint          - Run linting"
	@echo "  format        - Format code"
	@echo "  install       - Install dependencies"
	@echo "  clean         - Clean test outputs"

# Test targets
.PHONY: test
test:
	$(RUN) python -m pytest test/ -v

.PHONY: test-unit
test-unit:
	$(RUN) python -m pytest test/unit/ -v

.PHONY: test-integration
test-integration:
	$(RUN) python -m pytest test/integration/ -v

# Linting and formatting
.PHONY: lint
lint:
	$(RUN) ruff check .
	$(RUN) mypy kghub_downloader/

.PHONY: format
format:
	$(RUN) ruff format .
	$(RUN) ruff check --fix .

# Installation
.PHONY: install
install:
	poetry install

# Clean up
.PHONY: clean
clean:
	rm -rf test/output/
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete