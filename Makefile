.PHONY: setup setup-backend setup-frontend \
        build build-frontend \
        run run-backend run-frontend \
        run-reload run-backend-reload run-frontend-reload \
        clean clean-backend clean-frontend \
        lint lint-backend lint-frontend \
        format format-backend \
        test test-backend

# ==========================================
# Setup
# ==========================================
setup: setup-backend setup-frontend

setup-backend:
	cd backend && uv sync --all-extras

setup-frontend:
	cd frontend && npm install

# ==========================================
# Build
# ==========================================
build: build-frontend

build-frontend:
	cd frontend && npm run build

# ==========================================
# Run (Without Reload)
# ==========================================
run:
	@echo "Starting backend and frontend..."
	@trap 'kill 0' SIGINT; \
	$(MAKE) run-backend & \
	$(MAKE) run-frontend & \
	wait

run-backend:
	cd backend && uv run uvicorn yes_chef_mcp.app:app

run-frontend:
	cd frontend && npm run preview

# ==========================================
# Run (With Reload - Development)
# ==========================================
run-reload:
	@echo "Starting backend and frontend in development mode..."
	@trap 'kill 0' SIGINT; \
	$(MAKE) run-backend-reload & \
	$(MAKE) run-frontend-reload & \
	wait

run-backend-reload:
	cd backend && uv run uvicorn yes_chef_mcp.app:app --reload

run-frontend-reload:
	cd frontend && npm run dev

# ==========================================
# Testing & Linting
# ==========================================
test: test-backend

test-backend:
	cd backend && uv run pytest

lint: lint-backend lint-frontend

lint-backend:
	cd backend && uv run ruff check .
	cd backend && uv run mypy yes_chef_mcp/

lint-frontend:
	cd frontend && npm run typecheck

format: format-backend

format-backend:
	cd backend && uv run ruff format .

# ==========================================
# Clean
# ==========================================
clean: clean-backend clean-frontend

clean-backend:
	rm -rf backend/.venv
	rm -rf backend/.ruff_cache
	rm -rf backend/.mypy_cache
	find backend -type d -name "__pycache__" -exec rm -rf {} +

clean-frontend:
	rm -rf frontend/dist
	rm -rf frontend/node_modules
