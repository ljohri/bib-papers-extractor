# Troubleshooting

## "No bibliography found" / 0 references extracted

- Confirm the PDF is text-based, not a scanned image. OCR is not included in v1
  (see [`limitations.md`](limitations.md)).
- Run `uv run bibpdf extract-pdf path/to/paper.pdf --log-level DEBUG` to see which
  extractor backend was used and where detection failed.
- Some papers use unusual section titles (e.g. "Cited works"). The detector tries
  `^\s*(References|Bibliography|Works Cited|Cited Literature)\s*$`; consider
  pre-trimming the PDF to the references section.

## DOI not resolved

- The reference may have no DOI in metadata. Check `arxiv_id` resolution as a
  fallback.
- Crossref polite-pool requires `CROSSREF_MAILTO` set in `.env`.
- Try `--strategy deep` to query all four resolvers.

## API timeout / 429 rate-limited

- The pipeline retries with exponential backoff. Repeated 429s suggest you should
  lower `MAX_CONCURRENT_REQUESTS` in `.env`.
- Set `SEMANTIC_SCHOLAR_API_KEY` for higher S2 limits.

## PDF candidate rejected

- Most likely reason: source not on the allowlist, host on the deny-fragment list,
  or non-`https://` URL. See the run's `manifest.json` → `skipped[]` for the reason.
- This is intentional — see [`pdf-acquisition-policy.md`](pdf-acquisition-policy.md).

## Downloaded file is HTML, not PDF

The downloader rejects HTML responses by checking `Content-Type` and the `%PDF-`
magic bytes. If a candidate appears in the manifest as `failed` with
`error="non_pdf_response"`, the URL returned a landing page instead of the PDF.
This is treated as failure rather than silently saving HTML.

## Claude Desktop cannot start the MCP server

1. Confirm the `cwd` in your Claude Desktop config is the **absolute** path to the
   repository.
2. Run the same command manually: `cd <repo> && uv run python -m bibpdf_mcp.server`
   should print no errors and block waiting for stdio JSON-RPC.
3. Check Claude Desktop logs: `~/Library/Logs/Claude/mcp*.log` (macOS).
4. Make sure `uv` is on the `PATH` Claude sees — Claude does not source your shell
   profile. If needed, use the full path to `uv` (e.g. `/opt/homebrew/bin/uv`).

## Docker volume path issues on macOS

- Always use absolute paths in `-v` flags.
- For Docker Desktop, share the parent directory under Settings → Resources → File
  Sharing.
- Mount points inside the container are `/data` and `/cache`; your env vars (e.g.
  `CACHE_DB_PATH`) must point to those container paths.

## `uv` cannot find Python

```bash
uv python install 3.12
uv python list
```

If your system Python is older than 3.12, `uv` will download a managed interpreter.

## `uv` virtual environment mismatch

If `uv run` reports e.g. "package X not found":

```bash
rm -rf .venv
uv sync
```

If that doesn't help, ensure no Conda env is active and `PYTHONPATH` is unset.
