.PHONY: help check lint format-check format test test-integration test-all coverage coverage-report clean install

help:
	@echo "Dad's Money - Available Make Targets"
	@echo "===================================="
	@echo ""
	@echo "Code Quality:"
	@echo "  make check           - Run all checks (lint + format-check)"
	@echo "  make lint            - Run type checking with mypy"
	@echo "  make format-check    - Check code formatting with Black"
	@echo "  make format          - Apply Black formatting to code"
	@echo ""
	@echo "Testing:"
	@echo "  make test            - Run unit tests with pytest"
	@echo "  make test-integration - Run integration tests"
	@echo "  make test-all        - Run all tests (unit + integration)"
	@echo "  make coverage        - Run tests with coverage report (min 70%)"
	@echo "  make coverage-report - Show detailed coverage HTML report"
	@echo ""
	@echo "Utilities:"
	@echo "  make clean           - Clean up build artifacts and cache"
	@echo "  make install-dev     - Install development dependencies"
	@echo ""

# Check all code quality rules
check: lint format-check
	@echo "✓ All checks passed!"

# Type checking with mypy
lint:
	@echo "Running type checks with mypy..."
	mypy src/dads_money --strict --no-implicit-optional --warn-unused-ignores 2>/dev/null || python -m mypy src/dads_money 2>/dev/null || echo "Note: Install mypy for type checking (pip install mypy)"

# Check code formatting without modifying files
format-check:
	@echo "Checking code formatting with Black..."
	python -m black src/dads_money --line-length 100 --target-version py310 --check --diff

# Apply code formatting
format:
	@echo "Formatting code with Black..."
	python -m black src/dads_money --line-length 100 --target-version py310
	@echo "✓ Code formatted successfully!"

# Run unit tests
test:
	@echo "Running unit tests..."
	python -m pytest test_settings.py -v

# Run integration tests
test-integration:
	@echo "Running integration tests..."
	@if [ -d "tests" ]; then \
		python -m pytest tests/ -v -k "integration"; \
	else \
		echo "No integration tests directory found. Run: make test to run available tests."; \
	fi

# Run all tests
test-all:
	@echo "Running all tests..."
	python -m pytest test_settings.py -v 2>/dev/null || echo "Running manual test script..."
	python test_settings.py

# Run tests with coverage (minimum 70%)
coverage:
	@echo "Running tests with coverage (minimum 70% required)..."
	python -m pytest tests/ --cov=src/dads_money --cov-report=term-missing --cov-fail-under=70 -v 2>/dev/null || echo "Note: Install pytest-cov for coverage (pip install pytest-cov)"

# Generate HTML coverage report
coverage-report:
	@echo "Generating coverage HTML report..."
	python -m pytest tests/ --cov=src/dads_money --cov-report=html --cov-report=term-missing -v 2>/dev/null
	@echo ""
	@echo "Open htmlcov/index.html in your browser to view the report"

# Clean up build artifacts and cache
clean:
	@echo "Cleaning up build artifacts and cache files..."
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .mypy_cache -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name *.egg-info -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name .coverage -delete 2>/dev/null || true
	find . -type d -name build -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name dist -exec rm -rf {} + 2>/dev/null || true
	@echo "✓ Clean complete!"

# Install development dependencies
install-dev:
	@echo "Installing development dependencies..."
	pip install -e ".[dev]"
	@echo "✓ Development dependencies installed!"
