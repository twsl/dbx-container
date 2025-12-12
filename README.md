# dbx-container

[![Build](https://github.com/twsl/dbx-container/actions/workflows/build.yaml/badge.svg)](https://github.com/twsl/dbx-container/actions/workflows/build.yaml)
[![Documentation](https://github.com/twsl/dbx-container/actions/workflows/docs.yaml/badge.svg)](https://github.com/twsl/dbx-container/actions/workflows/docs.yaml)
[![Docs with MkDocs](https://img.shields.io/badge/MkDocs-docs?style=flat&logo=materialformkdocs&logoColor=white&color=%23526CFE)](https://squidfunk.github.io/mkdocs-material/)
[![Poetry](https://img.shields.io/endpoint?url=https://python-poetry.org/badge/v0.json)](https://python-poetry.org/)
[![linting: ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![pre-commit](https://img.shields.io/badge/pre--commit-enabled-brightgreen?logo=pre-commit)](.pre-commit-config.yaml)
[![Checked with pyright](https://microsoft.github.io/pyright/img/pyright_badge.svg)](https://microsoft.github.io/pyright/)
[![security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)
[![Semantic Versions](https://img.shields.io/badge/%20%20%F0%9F%93%A6%F0%9F%9A%80-semantic--versions-e10079.svg)](https://github.com/twsl/dbx-container/releases)
[![Copier](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/copier-org/copier/master/img/badge/badge-grayscale-border.json)](https://github.com/copier-org/copier)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

Create databricks runtime containers, [vibe coded](https://x.com/karpathy/status/1886192184808149383).

Docker images are losely based on the [container definitions](https://github.com/databricks/containers) and [runtime information](https://docs.databricks.com/aws/en/release-notes/runtime/).

## Features

- Generate Dockerfiles for all Databricks runtime versions
- Support for multiple image types: minimal, standard, python (all as GPU variants where applicable)
- LTS runtime support with ML variants
- Automated CI/CD pipeline for building and publishing images
- Multiple OS and Python version variations
- Built-in runtime metadata and version tracking

## Installation

With `pip`:

```bash
python -m pip install dbx-container
```

With [`poetry`](https://python-poetry.org/):

```bash
poetry add dbx-container
```

## How to use it

### Generate Dockerfiles

Generate Dockerfiles for all Databricks runtimes:

```bash
poetry run dbx-container build
```

Generate for a specific runtime:

```bash
poetry run dbx-container build --runtime-version "15.4 LTS"
```

Generate for a specific image type:

```bash
poetry run dbx-container build --image-type gpu
```

### List Available Runtimes

View all supported Databricks runtime versions:

```bash
poetry run dbx-container list
```

### Build Docker Images

Build all LTS images locally:

```bash
./scripts/build_images.sh
```

Build and push to a registry:

```bash
./scripts/build_images.sh --push --registry ghcr.io
```

### Use Pre-built Images

Pull from GitHub Container Registry:

```bash
docker pull ghcr.io/twsl/dbx-runtime:python-17.3-lts-ubuntu2404-py312
```

## Available Image Types

- **minimal** - Base Ubuntu with Java (non-runtime-specific)
- **minimal-gpu** - Base GPU image with CUDA and Java (non-runtime-specific)
- **standard** - Standard with SSH server and FUSE support (non-runtime-specific)
- **standard-gpu** - GPU standard with SSH and FUSE (non-runtime-specific)
- **python** - Python runtime with virtualenv (runtime-specific)
- **python-gpu** - GPU Python with CUDA support (runtime-specific)
- **gpu** - Standalone GPU-enabled container (non-runtime-specific)

Each LTS runtime includes:

- Base variant (standard runtime)
- ML variant (machine learning runtime)
- Multiple OS versions (Ubuntu 22.04, 24.04)
- Appropriate Python versions (3.8-3.12)

## CI/CD Pipeline

The project includes a GitHub Actions workflow that:

1. Automatically generates Dockerfiles for all LTS runtimes
2. Builds images in parallel using matrix strategy
3. Pushes to GitHub Container Registry on main branch
4. Supports manual triggering with filters

See [Docker Build Guide](docs/docs/docker-build.md) for detailed documentation.

## Docs

```bash
poetry run mkdocs build -f ./docs/mkdocs.yml -d ./_build/
```

## Update template

```bash
copier update --trust -A --vcs-ref=HEAD
```

## Credits

This project was generated with [![🚀 A generic python project template.](https://img.shields.io/badge/python--project--template-%F0%9F%9A%80-brightgreen)](https://github.com/twsl/python-project-template)
