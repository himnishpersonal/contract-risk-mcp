# contract-risk-analyzer

Contract Risk Analyzer is a FastMCP server + LangGraph workflow that ingests financial contract PDFs, extracts key clauses and obligations, flags known risk terms with severity, compares contract versions, and synthesizes everything into a structured risk brief for lawyers, risk teams, and operators who need fast, explainable contract triage.

The MCP tools accept either a local `file_path` or a remote `pdf_url`. For hosted deployments such as Railway, use `pdf_url` so the server can download the PDF into temporary storage before analysis.

## Architecture (high level)

```
PDF
  |
  v
FastMCP_Server
  |
  +--> extract_clauses
  +--> flag_risk_terms
  +--> summarize_obligations
  +--> compare_contracts
  |
  v
LangGraph_Agent (orchestrates tools)
  |
  v
RiskBrief (Pydantic structured output)
```

## Setup (local)

```bash
cd contract-risk-analyzer
cp .env.example .env
source .venv/bin/activate  # if you already created the project virtualenv
pip install -e ".[dev]"
python -m contract_risk_analyzer.server
```

- MCP endpoint: `http://localhost:8000/mcp`
- Health check: `http://localhost:8000/health`
- The `.env` file must contain `OPENAI_API_KEY`.

## Connecting from Claude Desktop (MCP client)

### Option A: Run as a local STDIO server (Claude Desktop spawns it)

In Claude Desktop, add an MCP server entry similar to:

```json
{
  "mcpServers": {
    "contract-risk-analyzer": {
      "command": "python",
      "args": ["-m", "contract_risk_analyzer.server"],
      "env": {
        "OPENAI_API_KEY": "YOUR_KEY_HERE"
      }
    }
  }
}
```

### Option B: Connect to the local HTTP server

If you run the server yourself (`python -m contract_risk_analyzer.server`), bridge Claude Desktop to the local MCP HTTP endpoint with `mcp-remote`:

```json
{
  "mcpServers": {
    "contract-risk-analyzer": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "http://127.0.0.1:8000/mcp",
        "--allow-http"
      ]
    }
  }
}
```

### Option C: Connect to the deployed Railway server

The deployed server is available at:

- Health check: `https://contract-risk-analyzer-production-410a.up.railway.app/health`
- MCP endpoint: `https://contract-risk-analyzer-production-410a.up.railway.app/mcp`

Claude Desktop config:

```json
{
  "mcpServers": {
    "contract-risk-analyzer": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "https://contract-risk-analyzer-production-410a.up.railway.app/mcp"
      ]
    }
  }
}
```

## Example tool calls

### Input source rules

For single-contract tools, provide exactly one of:

```json
{
  "file_path": "/app/samples/contract.pdf"
}
```

or:

```json
{
  "pdf_url": "https://example.com/contracts/contract.pdf"
}
```

For `compare_contracts`, provide exactly one source for each side:

```json
{
  "pdf_url_a": "https://example.com/contracts/v1.pdf",
  "pdf_url_b": "https://example.com/contracts/v2.pdf"
}
```

Remote PDFs are downloaded to temporary storage, capped at 50 MB per PDF, and deleted after each tool call.

### `extract_clauses`

Input:

```json
{
  "pdf_url": "https://example.com/contracts/isda.pdf",
  "clause_type": "termination events"
}
```

Sample output:

```json
[
  {
    "section_name": "ARTICLE_VII TERMINATION",
    "clause_type": "termination events",
    "raw_text": "…",
    "plain_english": "…",
    "page_references": [12, 13]
  }
]
```

### `flag_risk_terms`

Input:

```json
{ "pdf_url": "https://example.com/contracts/isda.pdf" }
```

Sample output:

```json
[
  {
    "term": "cross-default",
    "context": "…",
    "risk_explanation": "…",
    "severity": "high",
    "page_reference": 9
  }
]
```

### `summarize_obligations`

Input:

```json
{ "pdf_url": "https://example.com/contracts/isda.pdf" }
```

Sample output:

```json
[
  {
    "party": "Borrower",
    "obligations": ["Deliver monthly financial statements…"],
    "key_deadlines": ["Within 30 days after month-end…"],
    "conditions": ["So long as no Event of Default has occurred…"]
  }
]
```

### `compare_contracts`

Input:

```json
{
  "pdf_url_a": "https://example.com/contracts/v1.pdf",
  "pdf_url_b": "https://example.com/contracts/v2.pdf"
}
```

Sample output:

```json
{
  "added_clauses": ["New collateral top-up requirement…"],
  "removed_clauses": ["Removed cure period for payment default…"],
  "materially_changed_clauses": [
    {
      "section_name": "ARTICLE_IV EVENTS_OF_DEFAULT",
      "change_summary": "Acceleration now triggers immediately…",
      "risk_note": "Increases lender leverage; reduces borrower flexibility."
    }
  ],
  "risk_delta": "Overall risk increased for Borrower due to tighter default/acceleration terms."
}
```

## Deployment (Railway)

- **Build**: Railway will build the container from `Dockerfile`.
- **Run**: The container runs `python -m contract_risk_analyzer.server` and binds to `$PORT` (default `8000`).
- **Health check**: `GET /health` returns `{"status":"ok"}`.
- **Environment**: Set `OPENAI_API_KEY` in Railway service variables.
- **Current deployment**: `https://contract-risk-analyzer-production-410a.up.railway.app`.

## Tech stack

- FastMCP
- OpenAI GPT-4o (via `openai` SDK)
- PyMuPDF (`pymupdf`)
- Pydantic
- LangGraph
- Docker
- Railway
