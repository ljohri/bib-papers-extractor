# Docker

Docker is **optional**. The primary supported workflow is `uv` directly. Use Docker
when you want full isolation or to share a reproducible runtime.

## Build

```bash
docker build -t bibliography-pdf-mcp:latest .
```

## Run interactively (stdio MCP server)

```bash
docker run -i --rm \
  --env-file .env \
  -v "$PWD/data:/data" \
  -v "$PWD/cache:/cache" \
  bibliography-pdf-mcp:latest
```

The image's entrypoint is `uv run python -m bibpdf_mcp.server`.

## docker-compose

A `docker-compose.yml` is included for convenience:

```bash
docker compose run --rm bibpdf-mcp
```

It mounts `./data` and `./cache` from the host and reads env vars from `.env`.

## Volumes

| Host                | Container | Purpose |
|---|---|---|
| `./data`            | `/data`   | Input PDFs and run outputs. |
| `./cache`           | `/cache`  | SQLite cache of API responses. |

## Environment

The container expects the same env vars listed in [`installation.md`](installation.md).
For Claude Desktop, paths inside `env:` should match the **container** paths
(e.g. `CACHE_DB_PATH=/cache/bibpdf.sqlite`).

## Local debugging

Open a shell in the image:

```bash
docker run -it --rm --entrypoint /bin/bash bibliography-pdf-mcp:latest
# inside:
uv run bibpdf --help
uv run pytest -q
```
