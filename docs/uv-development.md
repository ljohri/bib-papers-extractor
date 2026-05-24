# Developing with `uv`

This project is fully managed by [`uv`](https://docs.astral.sh/uv/). You should
**not** need to manually create a virtualenv, run `pip`, or use Conda.

## Install `uv`

```bash
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Or with Homebrew
brew install uv
```

## Daily workflow

```bash
uv sync                       # create/update .venv from uv.lock
uv run bibpdf --help          # any command — uv runs inside .venv automatically
uv run python -m bibpdf_mcp.server
uv run pytest                 # run tests
uv run ruff check .           # lint
uv run ruff format .          # format
```

## Adding dependencies

```bash
uv add httpx                  # runtime dependency
uv add --dev pytest-cov       # dev-only
uv lock --upgrade             # bump lock file
uv sync                       # apply
```

## Resolving `.venv` issues

If anything looks wrong with the venv:

```bash
rm -rf .venv
uv sync
```

`uv sync --frozen` enforces the exact pins in `uv.lock` (use this in CI/Docker).

## Avoiding Conda conflicts

Conda's environment activation can pollute `PATH` and `PYTHONPATH`. Avoid:

- Running `uv` from inside a `conda activate` shell.
- Setting `CONDA_PREFIX` or `PYTHONHOME` env vars.

If `uv run` reports the wrong Python version, try:

```bash
deactivate || true
conda deactivate || true
unset PYTHONHOME PYTHONPATH
uv sync
uv run python --version
```

## Selecting a Python version

```bash
uv python install 3.12
uv venv --python 3.12
uv sync
```
