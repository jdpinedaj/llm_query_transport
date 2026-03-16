# Makefile for LLM Query Transport Project
# Natural language to SQL conversion for bike-sharing data

# Colors for output
BLUE = \033[0;34m
GREEN = \033[0;32m
YELLOW = \033[1;33m
RED = \033[0;31m
NC = \033[0m

SCHEMA_SQL = data/spider_data/database/bike_1/schema_postgres.sql

.PHONY: help run_app kill_app clean fix_ruff setup_db teardown_db evaluate

help:
	@echo "$(BLUE)LLM Query Transport - Makefile$(NC)"
	@echo ""
	@echo "$(GREEN)Available targets:$(NC)"
	@echo ""
	@echo "$(YELLOW)Application:$(NC)"
	@echo "  $(YELLOW)run_app$(NC)      - Setup database and run the Streamlit application"
	@echo "  $(YELLOW)kill_app$(NC)     - Kill Streamlit processes and drop the database"
	@echo ""
	@echo "$(YELLOW)Database:$(NC)"
	@echo "  $(YELLOW)setup_db$(NC)     - Create PostgreSQL database and load schema"
	@echo "  $(YELLOW)teardown_db$(NC)  - Drop the PostgreSQL database"
	@echo ""
	@echo "$(YELLOW)Evaluation:$(NC)"
	@echo "  $(YELLOW)evaluate$(NC)     - Run text-to-SQL evaluation metrics"
	@echo ""
	@echo "$(YELLOW)Code Quality:$(NC)"
	@echo "  $(YELLOW)fix_ruff$(NC)     - Auto-fix all ruff linting errors"
	@echo "  $(YELLOW)clean$(NC)        - Clean up temporary files and caches"
	@echo ""
	@echo "$(GREEN)Usage:$(NC)"
	@echo "  make run_app"
	@echo "  make kill_app"
	@echo "  make fix_ruff"
	@echo "  make evaluate"
	@echo "  make clean"

evaluate: setup_db  ## Run text-to-SQL evaluation metrics
	@printf "$(BLUE)Running evaluation metrics...$(NC)\n"
	uv run python -m src.evaluation.runner

setup_db:
	@printf "$(BLUE)Setting up PostgreSQL database...$(NC)\n"
	@bash -c '\
		set -e; \
		set -a; source .env 2>/dev/null; set +a; \
		DB_HOST=$${DB_HOST:-localhost}; \
		DB_PORT=$${DB_PORT:-5432}; \
		DB_USER=$${DB_USER:-postgres}; \
		DB_PASS=$${DB_PASS:-postgres}; \
		DB_NAME=$${DB_NAME:-bike_1}; \
		export PGPASSWORD=$$DB_PASS; \
		if ! pg_isready -h $$DB_HOST -p $$DB_PORT -q 2>/dev/null; then \
			printf "$(RED)Error: PostgreSQL is not running on $$DB_HOST:$$DB_PORT$(NC)\n"; \
			printf "$(YELLOW)Start it with: sudo service postgresql start$(NC)\n"; \
			exit 1; \
		fi; \
		if psql -h $$DB_HOST -p $$DB_PORT -U $$DB_USER -lqt | cut -d\| -f1 | grep -qw $$DB_NAME; then \
			ROW_COUNT=$$(psql -h $$DB_HOST -p $$DB_PORT -U $$DB_USER -d $$DB_NAME -tAc "SELECT COUNT(*) FROM station" 2>/dev/null || echo "0"); \
			if [ "$$ROW_COUNT" -gt 0 ] 2>/dev/null; then \
				printf "$(GREEN)Database $$DB_NAME already exists with data ($$ROW_COUNT stations). Skipping.$(NC)\n"; \
			else \
				printf "$(YELLOW)Database $$DB_NAME exists but is empty. Loading schema...$(NC)\n"; \
				psql -h $$DB_HOST -p $$DB_PORT -U $$DB_USER -d $$DB_NAME -f $(SCHEMA_SQL) > /dev/null; \
				printf "$(GREEN)Schema loaded successfully.$(NC)\n"; \
			fi; \
		else \
			printf "$(YELLOW)Creating database $$DB_NAME...$(NC)\n"; \
			createdb -h $$DB_HOST -p $$DB_PORT -U $$DB_USER $$DB_NAME; \
			printf "$(YELLOW)Loading schema...$(NC)\n"; \
			psql -h $$DB_HOST -p $$DB_PORT -U $$DB_USER -d $$DB_NAME -f $(SCHEMA_SQL) > /dev/null; \
			printf "$(GREEN)Database setup complete.$(NC)\n"; \
		fi \
	'

teardown_db:
	@printf "$(BLUE)Dropping PostgreSQL database...$(NC)\n"
	@bash -c '\
		set -a; source .env 2>/dev/null; set +a; \
		DB_HOST=$${DB_HOST:-localhost}; \
		DB_PORT=$${DB_PORT:-5432}; \
		DB_USER=$${DB_USER:-postgres}; \
		DB_PASS=$${DB_PASS:-postgres}; \
		DB_NAME=$${DB_NAME:-bike_1}; \
		export PGPASSWORD=$$DB_PASS; \
		if ! pg_isready -h $$DB_HOST -p $$DB_PORT -q 2>/dev/null; then \
			printf "$(YELLOW)PostgreSQL is not running. Nothing to drop.$(NC)\n"; \
			exit 0; \
		fi; \
		if psql -h $$DB_HOST -p $$DB_PORT -U $$DB_USER -lqt | cut -d\| -f1 | grep -qw $$DB_NAME; then \
			dropdb -h $$DB_HOST -p $$DB_PORT -U $$DB_USER $$DB_NAME; \
			printf "$(GREEN)Database $$DB_NAME dropped successfully.$(NC)\n"; \
		else \
			printf "$(YELLOW)Database $$DB_NAME does not exist. Nothing to drop.$(NC)\n"; \
		fi \
	'

run_app: setup_db
	@printf "$(BLUE)Starting Streamlit application...$(NC)\n"
	uv run streamlit run llm_query_app.py --server.headless=true --server.runOnSave=true

kill_app:
	@printf "$(BLUE)Searching for Streamlit processes...$(NC)\n"
	@bash -c '\
		pids=$$(ps aux | grep "streamlit run llm_query_app.py" | grep -v grep | awk "{print \$$2}"); \
		if [ -z "$$pids" ]; then \
			printf "$(GREEN)No running Streamlit processes found.$(NC)\n"; \
		else \
			count=$$(echo "$$pids" | wc -w); \
			printf "$(YELLOW)Found $$count Streamlit process(es):$(NC)\n"; \
			ps aux | grep "streamlit run llm_query_app.py" | grep -v grep | awk "{print \"  PID: \" \$$2 \" | CPU: \" \$$3 \"% | Memory: \" \$$4 \"%\"}"; \
			printf "$(RED)Killing processes...$(NC)\n"; \
			for pid in $$pids; do \
				kill -9 $$pid 2>/dev/null && printf "  $(RED)Killed PID: $$pid$(NC)\n" || printf "  $(YELLOW)Could not kill PID: $$pid$(NC)\n"; \
			done; \
		fi; \
		sleep 1; \
		remaining=$$(ps aux | grep "streamlit run llm_query_app.py" | grep -v grep | wc -l); \
		if [ "$$remaining" -eq 0 ]; then \
			printf "$(GREEN)All Streamlit processes terminated.$(NC)\n"; \
		else \
			printf "$(YELLOW)Warning: $$remaining process(es) still running.$(NC)\n"; \
		fi \
	'
	@$(MAKE) teardown_db

clean:
	@printf "$(BLUE)Cleaning up temporary files and caches...$(NC)\n"
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	@printf "$(GREEN)Cleanup completed.$(NC)\n"

fix_ruff:
	@printf "$(BLUE)Auto-fixing ruff linting errors...$(NC)\n"
	@printf "$(YELLOW)Step 1: Fixing imports...$(NC)\n"
	@uv run ruff check . --select I001 --fix
	@printf "$(YELLOW)Step 2: Applying all auto-fixable rules...$(NC)\n"
	@uv run ruff check . --fix --unsafe-fixes
	@printf "$(YELLOW)Step 3: Formatting...$(NC)\n"
	@uv run ruff format .
	@printf "$(GREEN)All auto-fixable ruff errors resolved!$(NC)\n"
	@printf "$(BLUE)Running final check...$(NC)\n"
	@uv run ruff check . --statistics
