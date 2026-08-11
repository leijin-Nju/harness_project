.PHONY: test lint demo

test:
	pytest -q

lint:
	ruff check src tests

demo:
	python scripts/mock_demo.py
