# Makefile for kghub-downloader

# Variables
RUN = poetry run

# Default target
.PHONY: help
help:
	@echo "Available targets:"
	@echo "  test          - Run all tests"
	@echo "  install       - Install dependencies"

# Test targets
.PHONY: test
test:
	$(RUN) python -m pytest test/ -v

# Installation
.PHONY: install
install:
	poetry install
