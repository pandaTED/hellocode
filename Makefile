.PHONY: build clean help install

help:
	@echo "Available commands:"
	@echo "  make install    - Install build dependencies"
	@echo "  make build      - Build hellocode executable"
	@echo "  make clean      - Clean build artifacts"

install:
	pip install nuitka ordered-set

build:
	python build.py

clean:
	rm -rf dist/ build/ *.spec
	rm -rf hellocode/__pycache__
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
