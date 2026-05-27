# A2A (Agent2Agent) setup

This project exposes the same bibliography pipeline as an **[A2A Protocol](https://a2a-protocol.org/)** agent over HTTP, in addition to the MCP stdio server.

## Run the A2A server

```bash
uv sync
cp .env.example .env   # set UNPAYWALL_EMAIL, paths, etc.

uv run bibpdf-a2a
# or: uv run python -m bibpdf_mcp.a2a
```

Defaults:

| Variable | Default | Purpose |
|----------|---------|---------|
| `A2A_HOST` | `127.0.0.1` | Bind address |
| `A2A_PORT` | `8080` | Listen port |
| `A2A_PUBLIC_URL` | `http://127.0.0.1:8080` | URL in the Agent Card |

## Discover the agent

Fetch the **Agent Card** (capability manifest):

```bash
curl -s http://127.0.0.1:8080/.well-known/agent.json | jq .
```

The card lists six **skills** (same operations as MCP tools):

| Skill ID | Description |
|----------|-------------|
| `extract_references_from_pdf` | Extract bibliography from a PDF |
| `parse_bibtex_file` | Parse a `.bib` file |
| `resolve_references` | Resolve metadata (Crossref, OpenAlex, S2, arXiv) |
| `find_public_pdfs` | Find legal OA PDF URLs |
| `download_public_pdfs` | Download approved PDFs |
| `process_paper_bibliography` | End-to-end pipeline |

## Send a task (JSON-RPC)

Clients send a **message** whose text is JSON specifying the skill and arguments:

```json
{
  "skill": "process_paper_bibliography",
  "arguments": {
    "pdf_path": "/absolute/path/to/paper.pdf",
    "output_dir": "/absolute/path/to/output/run-001",
    "strategy": "balanced"
  }
}
```

`output_dir` is optional when `DEFAULT_OUTPUT_DIR` is set in the server environment.

Use any A2A-compatible client (see [a2a-samples](https://github.com/a2aproject/a2a-samples)) or the SDK’s JSON-RPC `message/send` against `A2A_PUBLIC_URL`.

The agent responds with a task artifact containing JSON results (or an `error` object on failure).

## REST transport

The server also registers **HTTP+JSON/REST** routes at the same base URL (`create_rest_routes`). JSON-RPC is the primary binding advertised on the Agent Card.

## MCP vs A2A

| | MCP (`bibpdf_mcp.server`) | A2A (`bibpdf-a2a`) |
|--|---------------------------|---------------------|
| Transport | stdio | HTTP (JSON-RPC + REST) |
| Discovery | MCP tool list | Agent Card (`/.well-known/agent.json`) |
| Invocation | Tool calls | Tasks / messages with JSON skill payload |
| Use with | Claude Desktop, Cursor | A2A clients, multi-agent orchestrators |

Both share `bibpdf_mcp.tool_handlers` and `bibpdf_mcp.pipeline`.

## See also

- [`mcp-tools.md`](mcp-tools.md) — argument shapes per operation
- [`installation.md`](installation.md) — dependencies and env vars
