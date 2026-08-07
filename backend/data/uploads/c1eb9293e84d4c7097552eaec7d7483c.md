# 🔍 Investiga: Enterprise AI Investigation & Knowledge Intelligence Platform

[![Python 3.12+](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)](https://www.postgresql.org/)
[![Qdrant](https://img.shields.io/badge/Qdrant-Vector_DB-DC244C.svg)](https://qdrant.tech/)
[![Ollama](https://img.shields.io/badge/Ollama-Llama_3-black.svg)](https://ollama.ai/)
[![Gemini](https://img.shields.io/badge/Google_Gemini-2.5_Flash-4285F4.svg)](https://ai.google.dev/)

Investiga is an **enterprise-grade AI Knowledge Intelligence Platform** designed to help organizations ingest, understand, retrieve, and reason over large technical knowledge bases using **Retrieval-Augmented Generation (RAG)**.

Built using **Clean Architecture**, Investiga combines secure enterprise authentication, intelligent document ingestion, semantic search, hybrid retrieval, vector databases, and large language models into a modular AI platform suitable for production environments.

---

# 🚀 Core Features

## 🔐 Enterprise Identity & Access Management

- JWT Authentication
- Argon2id Password Hashing
- Refresh Token Rotation
- Role-Based Access Control (RBAC)
- Permission-based Authorization
- Multi-Tenant Ready Architecture
- Complete Authentication API

---

## 📚 Knowledge Management

- Document Upload
- Metadata Management
- Version Tracking
- Soft Deletes
- SHA-256 Duplicate Detection
- Enterprise Audit Trail

Supports

- PDF
- DOCX
- Markdown
- TXT
- JSON
- CSV

---

## 📄 Intelligent Document Processing

Automatic

- Text Extraction
- Metadata Extraction
- Unicode Normalization
- Noise Removal
- Paragraph Preservation
- Multi-Encoding Detection

Built on

- PyMuPDF
- python-docx
- Markdown parser

---

## ✂ Intelligent Chunking Engine

Six chunking strategies

- Adaptive
- Recursive
- Paragraph
- Sentence
- Markdown Header
- Fixed Character

Features

- Token-aware chunk sizing
- Chunk overlap
- Code block protection
- Table preservation
- URL preservation
- Deterministic UUID generation

---

## 🧠 Embedding Engine

Provider-agnostic embedding architecture supporting

- Sentence Transformers
- HuggingFace models
- Future OpenAI support

Default Model

**BAAI/bge-base-en-v1.5**

Features

- Adaptive batching
- Async embedding generation
- L2 normalization
- GPU auto detection
- Latency metrics

---

## 🗄 Vector Database

Powered by **Qdrant**

Features

- gRPC + HTTP fallback
- Metadata filtering
- Batch vector indexing
- Collection lifecycle management
- Multi-tenant payloads
- Similarity Search

---

## 🔎 Hybrid Retrieval Engine

Enterprise Hybrid Search combining

- Dense Vector Search
- BM25 Sparse Retrieval
- Reciprocal Rank Fusion (RRF)

Capabilities

- Metadata filtering
- Async concurrent retrieval
- Query preprocessing
- Score normalization
- Partial failure recovery
- Detailed retrieval telemetry

---

## 🤖 Enterprise RAG Engine

Supports multiple LLM providers

- Google Gemini
- Ollama
- Mock Provider

Features

- Context Builder
- Token Budgeting
- Prompt Strategies
- Citation Attribution
- Hallucination Guardrails
- Streaming Responses
- Runtime Provider Switching

Prompt Strategies

- Standard QA
- Investigative Analysis
- Executive Summary
- Extractive
- Concise

---

## 📊 Evaluation Framework

Enterprise evaluation suite providing

- Recall@K
- Precision@K
- MRR
- MAP
- nDCG
- Citation Coverage
- Faithfulness
- Hallucination Rate
- Provider Benchmarking
- Excel / CSV / Markdown Reports
- Notebook-ready DataFrames

---

# 🏗 Architecture

```text
Client
   │
   ▼
FastAPI REST API
   │
   ▼
Authentication & RBAC
   │
   ▼
Knowledge Management
   │
   ▼
Document Processing
   │
   ▼
Chunking Engine
   │
   ▼
Embedding Engine
   │
   ▼
Qdrant Vector Database
   │
   ▼
Hybrid Retrieval (Dense + BM25)
   │
   ▼
Enterprise RAG Engine
   │
   ▼
Gemini / Ollama
```

---

# 📂 Project Structure

```text
backend/
│
├── api/
├── auth/
├── chunking/
├── document_processing/
├── embeddings/
├── evaluation/
├── ingestion/
├── knowledge/
├── rag/
├── retrieval/
├── storage/
├── vectorstore/
│
├── core/
├── db/
├── tests/
└── main.py
```

---

# ⚙ Technology Stack

### Backend

- Python
- FastAPI
- SQLAlchemy
- PostgreSQL
- Alembic

### AI

- Sentence Transformers
- BAAI/bge-base-en-v1.5
- Google Gemini
- Ollama
- tiktoken

### Search

- Qdrant
- BM25
- Reciprocal Rank Fusion

### Infrastructure

- Docker
- AsyncIO
- Pydantic v2

### Quality

- Pytest
- Ruff
- MyPy

---

# 📈 Evaluation

The platform includes an enterprise evaluation framework capable of benchmarking retrieval quality and generation performance across multiple LLM providers.

Supported metrics include

- Recall@K
- Precision@K
- MRR
- MAP
- nDCG
- Citation Coverage
- Hallucination Rate
- Faithfulness
- Context Utilization

Evaluation reports can be exported as

- Markdown
- JSON
- CSV
- Excel
- Notebook-ready DataFrames

---

# 🚀 Getting Started

```bash
git clone https://github.com/yourusername/Investiga.git

cd Investiga/backend

python -m venv .venv

source .venv/bin/activate
# Windows
.venv\Scripts\activate

pip install -r requirements.txt
```

Run PostgreSQL and Qdrant

```bash
docker compose up -d
```

Run the API

```bash
uvicorn app.main:app --reload
```

---

# 📷 Screenshots

## System Architecture

```markdown
<p align="center">
<img src="docs/images/architecture.png" width="900">
</p>
```

## Document Ingestion Pipeline

```markdown
<p align="center">
<img src="docs/images/pipeline.png" width="900">
</p>
```

## Retrieval Evaluation

```markdown
<p align="center">
<img src="docs/images/retrieval_metrics.png" width="900">
</p>
```

## RAG Benchmark Dashboard

```markdown
<p align="center">
<img src="docs/images/evaluation_dashboard.png" width="900">
</p>
```

---

# 📄 License

MIT License

---

> **Investiga demonstrates the design and implementation of a production-ready Enterprise Retrieval-Augmented Generation (RAG) platform, integrating secure identity management, intelligent document processing, hybrid search, vector databases, and multi-provider LLM orchestration within a modular Clean Architecture.**