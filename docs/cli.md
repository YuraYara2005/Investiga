# Investiga Operational CLI Suite

The Investiga Operational CLI Suite provides a terminal interface for operating, testing, evaluating, and benchmarking the Investiga Enterprise Incident Investigation & RAG Platform.

Built with [Rich](https://github.com/Textualize/rich), the CLI layer orchestrates all existing backend subsystems—ETL ingestion, document processing, intelligent chunking, embeddings, Qdrant vector storage, hybrid retrieval, enterprise RAG, and evaluation metrics—through a dependency injection architecture.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Prerequisites & Setup](#prerequisites--setup)
3. [CLI Applications](#cli-applications)
   - [1. Knowledge Ingestion CLI (`ingest_knowledge.py`)](#1-knowledge-ingestion-cli-ingest_knowledgepy)
   - [2. Interactive RAG Chat CLI (`chat.py`)](#2-interactive-rag-chat-cli-chatpy)
   - [3. Evaluation Framework Runner (`run_evaluation.py`)](#3-evaluation-framework-runner-run_evaluationpy)
   - [4. Multi-Provider Benchmark Tool (`benchmark_providers.py`)](#4-multi-provider-benchmark-tool-benchmark_providerspy)
4. [Dependency Injection & Programmatic Usage](#dependency-injection--programmatic-usage)
5. [Configuration & Environment Variables](#configuration--environment-variables)
6. [Supported Formats & Datasets](#supported-formats--datasets)

---

## Architecture Overview

The operational CLI layer resides in `scripts/` and bridges command-line execution with the Clean Architecture backend:

```
Investiga Operational CLI Architecture
┌────────────────────────────────────────────────────────────────────────┐
│                          CLI Applications                              │
│   ingest_knowledge.py   chat.py   run_evaluation.py   benchmark...py   │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│                    scripts.common Shared Infrastructure                │
│    console.py (Rich UI)     factory.py (DI)     helpers.py (Utils)     │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
┌───────────────────────────────────▼────────────────────────────────────┐
│                       Investiga Core Backend Subsystems                │
│  ETL  •  DocProcessing  •  Chunking  •  Embeddings  •  VectorStore     │
│             Retrieval  •  RAG Engine  •  Evaluation & Analytics       │
└────────────────────────────────────────────────────────────────────────┘
```

### Key Highlights

- **Dependency Injection**: Services are assembled via `scripts/common/factory.py`, reusing existing backend business logic without code duplication.
- **Enterprise Terminal UI**: Professional Rich formatting featuring telemetry cards, animated progress bars, syntax-highlighted code blocks, and structured ASCII tables.
- **Resilient Execution**: Graceful `Ctrl+C` interrupt handlers, automatic UTF-8 terminal encoding, and offline fallbacks.

---

## Prerequisites & Setup

Ensure you have Python 3.11+ installed and activate your virtual environment:

```bash
# Clone and navigate to repository
cd Investiga

# Install dependencies
pip install -r backend/requirements.txt

# Configure environment variables
cp backend/.env.example backend/.env
```

Ensure Qdrant and PostgreSQL are running (optional if using mock mode for testing):

```bash
docker-compose up -d
```

---

## CLI Applications

### 1. Knowledge Ingestion CLI (`ingest_knowledge.py`)

Recursively scans directories or single files, loads documents via the ETL subsystem, segments content with intelligent chunking, generates embeddings, and persists knowledge into PostgreSQL and Qdrant collections.

#### Usage

```bash
# Ingest local documentation directory
python scripts/ingest_knowledge.py --source docs/ --category Engineering

# Perform a dry-run without writing to database or vector store
python scripts/ingest_knowledge.py --source data/samples/ --dry-run

# Limit processing to 10 files with custom chunk batch sizes
python scripts/ingest_knowledge.py --source /path/to/docs --max-files 10 --batch-size 32
```

#### Command Options

| Option | Flag | Default | Description |
|---|---|---|---|
| `--source` | `-s` | *Required* | Path to source file or directory for ingestion. |
| `--category` | `-c` | `General` | Category tag for metadata classification. |
| `--recursive` / `--no-recursive` | `-r` | `True` | Recursively scan subdirectories. |
| `--batch-size` | `-b` | `50` | Number of chunks per embedding/upsert batch. |
| `--max-files` | `-l` | `None` | Maximum number of files to process. |
| `--dry-run` | `-d` | `False` | Parse and chunk documents without database persistence. |
| `--verbose` | `-v` | `False` | Enable verbose diagnostic logging. |

---

### 2. Interactive RAG Chat CLI (`chat.py`)

An interactive terminal REPL for querying the Investiga knowledge base with multi-provider LLM support, live streaming, retrieved context exploration, and citation inspection.

#### Usage

```bash
# Start chat with default provider (Mock / configured LLM)
python scripts/chat.py

# Start chat using Gemini provider and technical strategy
python scripts/chat.py --provider gemini --strategy incident_investigation --top-k 5

# Start chat using local Ollama model
python scripts/chat.py --provider ollama --model llama3:8b
```

#### In-Session Slash Commands

While in the chat prompt (`Investiga >`), you can execute control commands:

| Command | Description |
|---|---|
| `/help` | Show interactive help and active configuration. |
| `/provider <name> [model]` | Switch active LLM provider (`gemini`, `ollama`, `mock`) and optional model. |
| `/strategy <name>` | Switch prompt synthesis strategy (`standard_qa`, `incident_investigation`, `concise`, etc.). |
| `/context` | Toggle display of raw retrieved document chunks and similarity scores. |
| `/citations` | Toggle display of structured citation references. |
| `/metrics` | Toggle inference telemetry (LLM latency, total response time, token counts). |
| `/history` | Display conversation history in the current session. |
| `/clear` | Reset conversation message history. |
| `/exit`, `/quit`, `exit` | Terminate the chat session. |

---

### 3. Evaluation Framework Runner (`run_evaluation.py`)

Executes the RAG Evaluation Framework against benchmark datasets, measuring retrieval quality (Recall@K, MRR, nDCG, MAP) and generation fidelity (Faithfulness, Citation Coverage, Hallucination Detection, Answer Relevancy).

#### Usage

```bash
# Run evaluation using built-in benchmark dataset
python scripts/run_evaluation.py --provider mock

# Evaluate against a custom JSON/JSONL/CSV dataset
python scripts/run_evaluation.py --dataset tests/data/eval_dataset.json --provider gemini

# Specify custom K thresholds and concurrent worker tasks
python scripts/run_evaluation.py --provider ollama --k-values 1,3,5,10 --concurrency 8 --output-dir evaluation_runs/march_benchmark
```

#### Generated Report Artifacts

Each evaluation run automatically exports structured artifacts to `--output-dir`:

- `report.json` — Complete JSON report including run metadata, metrics, and per-sample results.
- `report.md` — Human-readable Markdown summary with tables and scorecards.
- `report.csv` — Tabular CSV format suitable for data analysis.
- `report.xlsx` — Multi-sheet Excel workbook (Overview, Metrics, Per-Sample Traces).
- `leaderboard.csv` — Single-row summary formatted for benchmark leaderboards.
- `trace.json` — Detailed per-query retrieval and generation traces.

---

### 4. Multi-Provider Benchmark Tool (`benchmark_providers.py`)

Executes automated side-by-side benchmarking across multiple LLM providers (`gemini`, `ollama`, `mock`), calculates weighted composite quality scores, and ranks providers in an interactive terminal leaderboard.

#### Usage

```bash
# Benchmark mock provider against built-in test suite
python scripts/benchmark_providers.py --providers mock

# Benchmark all configured providers side-by-side
python scripts/benchmark_providers.py --providers all --concurrency 4

# Benchmark specific providers with custom dataset
python scripts/benchmark_providers.py --providers gemini,ollama --dataset eval_suite.jsonl --output-dir benchmark_runs/q1_comparison
```

#### Benchmark Scoring Weights

The composite leaderboard score is calculated using weighted metrics:

$$\text{Composite Score} = 0.25 \times \text{Faithfulness} + 0.20 \times (1 - \text{Hallucination Rate}) + 0.15 \times \text{Citation Coverage} + 0.15 \times \text{Recall@5} + 0.15 \times (1 - \text{Normalized Latency}) + 0.10 \times \text{Relevancy}$$

---

## Dependency Injection & Programmatic Usage

All CLI scripts use `scripts/common/factory.py` for service instantiation:

```python
from scripts.common.factory import (
    create_cli_rag_service,
    create_cli_evaluator,
    create_cli_benchmark,
)

# Instantiate RAG Service with configured providers
rag_service = create_cli_rag_service()

# Execute query programmatically
response = await rag_service.query("What caused incident INC-492?")
print(response.answer)
```

---

## Configuration & Environment Variables

The CLI suite respects settings configured in `.env` or system environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | `""` | Google Gemini API key for cloud LLM inference. |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama service endpoint for local LLM inference. |
| `EMBEDDING_MODEL_NAME` | `BAAI/bge-base-en-v1.5` | SentenceTransformers model for dense embeddings. |
| `QDRANT_HOST` | `localhost` | Qdrant vector database host. |
| `QDRANT_PORT` | `6333` | Qdrant vector database HTTP port. |
| `INVESTIGA_VERBOSE` | `0` | Set to `1` to enable verbose diagnostic logs. |
| `INVESTIGA_OFFLINE` | `0` | Set to `1` to force mock embeddings and offline mode. |
