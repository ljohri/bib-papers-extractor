# Cursor setup

Cursor reads MCP server config from `~/.cursor/mcp.json` (global) or
`<workspace>/.cursor/mcp.json` (per-workspace).

## Recommended config

```json
{
  "mcpServers": {
    "bibliography-pdf": {
      "command": "uv",
      "args": ["run", "python", "-m", "bibpdf_mcp.server"],
      "cwd": "/absolute/path/to/bib-papers-extractor",
      "env": {
        "UNPAYWALL_EMAIL": "your-email@example.com",
        "CROSSREF_MAILTO": "your-email@example.com",
        "DEFAULT_OUTPUT_DIR": "/absolute/path/to/bib-papers-extractor/data/output"
      }
    }
  }
}
```

After saving, restart Cursor (or reload the MCP config). The 6 tools will appear
under the bibliography-pdf server.

## Example prompts

```
Use the bibliography-pdf MCP server.

Input paper: /data/input/source-paper.pdf

Extract the bibliography, resolve all references, download all public PDFs,
and create a markdown report in /data/output/source-paper-run.
```

```
Run process_paper_bibliography on /data/input/attention.pdf with strategy="deep"
and output to /data/output/attention-run.
```
