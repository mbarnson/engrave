.PHONY: setup test lint format

UV := uv

# Single-command onboarding
setup:
	@echo "=== Engrave Setup ==="
	# Install Python dependencies
	$(UV) sync
	# Install pre-commit hooks
	$(UV) run pre-commit install
	# Verify LilyPond
	@if command -v lilypond >/dev/null 2>&1; then \
		LILY_VERSION=$$(lilypond --version 2>&1 | head -1 | grep -oE '[0-9]+\.[0-9]+'); \
		echo "LilyPond found: $$LILY_VERSION"; \
	else \
		echo "WARNING: LilyPond not found."; \
		if [ "$$(uname)" = "Darwin" ]; then \
			echo "Install with: brew install lilypond"; \
		elif [ -f /etc/alpine-release ] || busybox --help >/dev/null 2>&1; then \
			echo "Detected musl/Alpine. Install with: apk add lilypond"; \
		else \
			echo "Install with: sudo apt-get install lilypond"; \
		fi; \
	fi
	@echo "=== Setup Complete ==="

test:
	$(UV) run pytest tests/ -v --cov=engrave --cov-report=term-missing

lint:
	$(UV) run ruff check src/ tests/
	$(UV) run ruff format --check src/ tests/

format:
	$(UV) run ruff check --fix src/ tests/
	$(UV) run ruff format src/ tests/
