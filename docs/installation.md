# Installation

## Prerequisites

- Python **3.12+**
- [`uv`](https://docs.astral.sh/uv/) — fast Python package manager

Install `uv`:

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or with Homebrew
brew install uv
```

## Clone & install

```bash
git clone git@github.com:ljohri/bib-papers-extractor.git
cd bib-papers-extractor
uv sync
cp .env.example .env
```

`uv sync` will:

1. Create `.venv/` if it doesn't exist.
2. Install all runtime + dev dependencies pinned in `uv.lock`.
3. Install the `bibpdf` console script into the venv.

## Quick smoke test

```bash
uv run bibpdf --help
uv run python -m bibpdf_mcp.server --help   # (server uses stdio when run without --help)
uv run pytest -q
```

## Updating dependencies

```bash
uv add <package>
uv add --dev <package>
uv lock --upgrade
uv sync
```

## See also

- [`uv-development.md`](uv-development.md) — full dev workflow
- [`docker.md`](docker.md) — optional Docker runtime
- [`troubleshooting.md`](troubleshooting.md)
