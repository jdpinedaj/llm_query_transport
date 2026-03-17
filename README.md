<!-- pandoc README.md -s -o README.docx -->

# LLM Query Transport

![Python](https://img.shields.io/badge/python-3670A0?style=for-the-badge&logo=python&logoColor=ffdd54)
![Postgres](https://img.shields.io/badge/postgres-%23316192.svg?style=for-the-badge&logo=postgresql&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=for-the-badge&logo=langchain&logoColor=white)

<hr>

LLM Query Transport is a natural language to SQL conversion tool for bike-sharing data. It allows users to ask questions in plain English and get answers from a PostgreSQL database using LLM-powered query generation.

## Description

### Key Features

- **Natural Language to SQL** — Ask questions in plain English, get SQL queries generated automatically
- **Few-Shot Learning** — Uses FAISS-based semantic similarity to select the most relevant examples for query generation
- **Query Refinement** — Optional iterative refinement process for more accurate SQL generation
- **Safe Execution** — Only allows SELECT/WITH statements; blocks all DML/DDL operations
- **Natural Language Results** — Transforms raw query results back into human-readable answers
- **Chat History with Memory Window** — Maintains conversation context with a configurable sliding window to control token usage
- **CSV Download** — Export query results as downloadable CSV files
- **Structured Logging** — Colored, structured logs via structlog with callsite info

<hr>

## Architecture

The project follows a **Hexagonal Architecture** (Ports & Adapters) pattern:

```
src/
├── domain/                          # Business logic interfaces
│   ├── ports.py                     # Abstract interfaces (SessionManager, ConfigProvider, UINotifier)
│   └── schemas.py                   # Pydantic data models
│
├── application/services/            # Use cases
│   └── chat_orchestrator.py         # Main pipeline orchestration
│
├── infrastructure/                  # Concrete implementations
│   ├── database/
│   │   └── postgres_adapter.py      # PostgreSQL connection & safe query execution
│   ├── llm/
│   │   ├── sql_query_generator.py   # SQL generation with Few-Shot prompting
│   │   ├── natural_language_transformer.py  # Results → natural language
│   │   └── chat_history_collector.py        # Memory window chat history
│   ├── ui/
│   │   ├── streamlit_orchestrator.py  # Streamlit wrapper with @st.fragment()
│   │   └── streamlit_helpers.py       # UI utilities
│   ├── session_adapters.py          # Session state implementations
│   └── config_adapters.py           # Configuration providers
│
├── evaluation/                      # Pipeline evaluation
│   ├── metrics.py                   # EX, VER, latency, component matching
│   ├── harness.py                   # Test case runner
│   ├── visualization.py            # Publication-ready figures (PNG + SVG)
│   └── runner.py                    # CLI entry point (make evaluate)
│
└── config/
    ├── settings.py                  # Central configuration loader
    ├── app_config.yml               # Application parameters
    └── prompts/
        ├── prompt_loader.py         # YAML-based prompt management
        ├── sql_generation.yml       # SQL generation prompts
        ├── contexts.yml             # Table schemas, context & few-shot examples
        └── natural_language_transform.yml  # Result transformation prompts
```

### Pipeline Flow

```
User Question
     │
     ▼
┌─────────────────────┐
│  1. Connect to DB   │  PostgreSQLAdapter
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│  2. Generate SQL    │  SQLQueryGenerator + Few-Shot + FAISS
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│  3. Execute Query   │  Safe execution (SELECT/WITH only)
└─────────┬───────────┘
          ▼
┌─────────────────────┐
│  4. Transform to NL │  NaturalLanguageTransformer
└─────────┬───────────┘
          ▼
   Natural Language Answer
```

<hr>

## Getting Started

### Prerequisites

- Python 3.10 - 3.12
- [uv](https://docs.astral.sh/uv/) package manager
- PostgreSQL server (local or remote)
- OpenAI API key

### Installation

```bash
# Clone the repository
git clone <repo-url>
cd llm_query_transport

# Install dependencies
uv sync
```

### Environment Configuration

Create a `.env` file in the project root:

```env
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5.2-2025-12-11

# PostgreSQL connection
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASS=postgres
DB_NAME=bike_1

# LangSmith (optional)
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your_key
LANGCHAIN_PROJECT=llm-query-transport
```

Alternatively, create `.streamlit/secrets.toml`:

```toml
OPENAI_API_KEY = "sk-..."
```

### Running the App

```bash
make run_app
```

This command automatically:
1. Creates the PostgreSQL database if it doesn't exist
2. Loads the schema and seed data (~22K rows) if the database is empty
3. Starts the Streamlit application

Open [http://localhost:8501](http://localhost:8501) in your browser.

### Stopping the App

```bash
make kill_app
```

This command:
1. Kills all running Streamlit processes
2. Drops the PostgreSQL database

<hr>

## Available Commands

| Command | Description |
|---------|-------------|
| `make run_app` | Setup database (if needed) and start the Streamlit application |
| `make kill_app` | Drop the database and stop all Streamlit processes |
| `make evaluate` | Run text-to-SQL evaluation metrics (EX, VER, latency, component matching) |
| `make setup_db` | Create the PostgreSQL database and load schema only |
| `make teardown_db` | Drop the PostgreSQL database only |
| `make fix_ruff` | Auto-fix linting errors and format code |
| `make clean` | Remove cache files and temporary directories |
| `make help` | Show all available targets |

<hr>

## Database

The project uses a **bike-sharing dataset** (Bike 1) with 4 tables:

| Table | Description | Rows |
|-------|-------------|------|
| `station` | Bike station locations (name, lat/long, city, dock count) | 70 |
| `status` | Real-time bike/dock availability per station | 8,487 |
| `trip` | Individual bike trips (duration, stations, subscription) | 9,959 |
| `weather` | Daily weather data (temperature, humidity, wind, events) | 3,665 |

### Example Queries

- *"Get the average duration of trips grouped by zip codes"*
- *"How many trips started from station 63?"*
- *"What was the maximum temperature on 2013-08-29 for zip code 94107?"*
- *"List all stations in San Jose with their dock counts"*
- *"How did weather events impact ridership in August 2015?"*

<hr>

## Configuration

All application parameters are centralized in `src/config/app_config.yml`. Environment variables (`.env`) override database defaults.

### Models

| Parameter | Description | Default |
|-----------|-------------|---------|
| `model_to_use` | LLM provider | `openai` |
| `openai_model_generation_refinement` | Model for SQL generation (overridden by `OPENAI_MODEL` env var) | `gpt-5.2-2025-12-11` |
| `openai_model_transformation` | Model for NL transformation | `gpt-4-turbo` |
| `openai_embedding_model` | Model for embeddings | `text-embedding-3-large` |
| `reasoning_effort_generation` | Reasoning effort for GPT-5.x SQL generation | `low` |
| `reasoning_effort_transformation` | Reasoning effort for GPT-5.x NL transformation | `low` |
| `max_completion_tokens` | Max completion tokens for GPT-5.x models | `16384` |
| `temperature_generation_refinement` | Temperature for non-GPT-5 SQL generation | `0.1` |
| `temperature_transformation` | Temperature for non-GPT-5 NL transformation | `0.4` |

> **Note:** GPT-5.x reasoning models use `reasoning_effort` instead of `temperature`/`top_p`. The system auto-detects the model family and applies the correct parameters.

### Database

| Parameter | Description | Default |
|-----------|-------------|---------|
| `database.host` | PostgreSQL host (overridden by `DB_HOST` env var) | `localhost` |
| `database.port` | PostgreSQL port (overridden by `DB_PORT` env var) | `5432` |
| `database.name` | Database name (overridden by `DB_NAME` env var) | `bike_1` |

### Query Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `decimal_places` | Decimal precision for numeric results | `4` |
| `sample_size` | Max rows sampled for NL transformation | `50` |
| `few_shot_k` | Number of few-shot examples retrieved via FAISS | `5` |
| `top_k` | Top K parameter for SQL generation chain | `1` |
| `memory_window_size` | Number of recent interactions kept in context | `5` |

### UI

| Parameter | Description | Default |
|-----------|-------------|---------|
| `page_title` | Browser tab title | `LLM Query Transport` |
| `logo_width` | Logo image width (px) | `180` |
| `container_height` | Height of info and history panels (px) | `700` |
| `input_height` | Text input area height (px) | `150` |
| `default_query` | Pre-filled query example | `Get the average duration...` |
| `welcome_message` | Initial assistant greeting | `Hello! Ask me any question...` |
| `csv_filename_prefix` | Prefix for downloaded CSV files | `query_results` |

### Developer

| Parameter | Description | Default |
|-----------|-------------|---------|
| `include_refinement_process` | Enable SQL refinement step | `false` |
| `show_developer_comments` | Show internal queries in chat | `false` |
| `show_refined_query` | Show refined SQL in chat | `false` |
| `use_examples_vector_database` | Enable few-shot with FAISS | `true` |
| `analysis_langsmith` | Enable LangSmith tracing | `true` |

### Structured Logging

Logs use **structlog** with colored output in local environments:

```
[INFO] [chat_history_collector.py] [line:48] Memory stored
[INFO] [chat_history_collector.py] [line:77] Memory window applied  total_messages=8  window_size=5  discarded=3
[INFO] [sql_query_generator.py] [line:79] Generating SQL query for: How many trips...
```

Controlled via environment variables: `LOG_LEVEL` (default `INFO`), `ENVIRONMENT` (default `LOCAL`).


<hr>

## Evaluation Metrics

The pipeline is evaluated using state-of-the-art text-to-SQL metrics via `src/evaluation/`.

### Test Set

200 question/gold-SQL pairs (distinct from the 15 few-shot examples), organized by difficulty:

| Difficulty | Count | Description |
|------------|-------|-------------|
| Easy | 70 | Single table queries: COUNT, MIN, MAX, DISTINCT, simple WHERE |
| Medium | 70 | GROUP BY, ORDER BY, LIMIT, HAVING, date extraction, VARCHAR filters |
| Hard | 60 | Multi-table JOINs with aggregation, CASE, subqueries, city-pair analysis |

### Metrics

| Metric | Description |
|--------|-------------|
| **Execution Accuracy (EX)** | Percentage of generated queries that return the same result set as the gold SQL |
| **Valid Execution Rate (VER)** | Percentage of generated queries that execute without errors |
| **Latency** | Response time per pipeline stage (SQL generation, execution, NL transformation) — mean, median, p95 |
| **Component Matching** | Precision, Recall, and F1 per SQL clause (SELECT, WHERE, GROUP BY, ORDER BY, JOIN, aggregation) |

### Baseline Comparison

Two prompting modes are compared using the same test set:

- **Few-Shot + FAISS** — Retrieves the k most semantically similar examples via FAISS and includes them in the prompt
- **Simple Prompting** — Uses only the table schema and question, with no examples or domain context

### Running the Evaluation

```bash
make evaluate
```

This runs both prompting modes (Few-Shot + FAISS and Simple Prompting), prints all metrics to the console, and saves output to `results/evaluation/`:
- Figures: `execution_accuracy.png/.svg`, `latency_distribution.png/.svg`, `component_matching_heatmap.png/.svg`, `overall_comparison.png/.svg`
- Raw results: `evaluation_results.json`
<hr>

## Tech Stack

- **LLM Framework**: LangChain 0.2.x
- **LLM Provider**: OpenAI (GPT-5.2 for SQL generation, GPT-4-turbo for NL transformation)
- **Embeddings**: OpenAI text-embedding-3-large + FAISS
- **Database**: PostgreSQL + SQLAlchemy
- **Frontend**: Streamlit
- **Package Manager**: uv
- **Logging**: structlog (colored, structured)
- **Linter/Formatter**: Ruff
- **Data Validation**: Pydantic v2
