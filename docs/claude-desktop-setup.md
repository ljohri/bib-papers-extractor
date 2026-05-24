# Claude Desktop setup

The recommended local setup runs the server through `uv` directly — no Docker needed.

## Locate your config

| Platform | Path |
|---|---|
| macOS    | `~/Library/Application Support/Claude/claude_desktop_config.json` |
| Windows  | `%APPDATA%\Claude\claude_desktop_config.json` |
| Linux    | `~/.config/Claude/claude_desktop_config.json` |

## Recommended config (uv, local)

```json
{
  "mcpServers": {
    "bibliography-pdf": {
      "command": "uv",
      "args": [
        "run",
        "python",
        "-m",
        "bibpdf_mcp.server"
      ],
      "cwd": "/absolute/path/to/bib-papers-extractor",
      "env": {
        "UNPAYWALL_EMAIL": "your-email@example.com",
        "CROSSREF_MAILTO": "your-email@example.com",
        "CACHE_DB_PATH": "/absolute/path/to/bib-papers-extractor/cache/bibpdf.sqlite",
        "DEFAULT_INPUT_DIR": "/absolute/path/to/bib-papers-extractor/data/input",
        "DEFAULT_INPUT_PDF": "/absolute/path/to/your/paper.pdf",
        "DEFAULT_OUTPUT_DIR": "/absolute/path/to/bib-papers-extractor/data/output"
      }
    }
  }
}
```

> Use **absolute** paths. Replace `/absolute/path/to/...` with your real clone path.

## Optional config (Docker)

```json
{
  "mcpServers": {
    "bibliography-pdf": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "--env-file",
        "/absolute/path/to/bib-papers-extractor/.env",
        "-v",
        "/absolute/path/to/bib-papers-extractor/data:/data",
        "-v",
        "/absolute/path/to/bib-papers-extractor/cache:/cache",
        "bibliography-pdf-mcp:latest"
      ]
    }
  }
}
```

Build the image first: `docker build -t bibliography-pdf-mcp:latest .`

## Verifying

After saving the config, restart Claude Desktop. The bibliography tools should appear
in the tool picker. Try:

> Use the bibliography-pdf MCP server. Extract references from `/data/input/paper.pdf`.
