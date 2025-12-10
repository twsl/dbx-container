# Docker Image Building Guide

This guide explains how to build and use Databricks runtime Docker images.

## Overview

The `dbx-container` project generates Dockerfiles for multiple Databricks runtime versions and image types:

### Image Types

The project provides two parallel dependency chains:

**Standard Chain** (Ubuntu-based):

1. **minimal** - Minimal Ubuntu 24.04 container with Java

   - Base Ubuntu with essential tools
   - Azul Zulu JDK 8 and 17
   - Tag format: `dbx-runtime:minimal`

2. **python** - Python-enabled container with virtualenv support

   - Extends minimal image
   - Python installation with pip, setuptools, wheel
   - virtualenv for isolated environments
   - Common Python libraries for Databricks
   - Runtime metadata labels
   - Tag format: `dbx-runtime:python-py{version}` (e.g., `python-py312`)

3. **dbfsfuse** - Python container with DBFS FUSE capabilities

   - Extends python image
   - DBFS filesystem mounting support
   - Tag format: `dbx-runtime:dbfsfuse-py{version}`

4. **standard** - Standard container with SSH server support
   - Extends dbfsfuse image
   - SSH server for remote access
   - Tag format: `dbx-runtime:standard-py{version}`

**GPU Chain** (NVIDIA CUDA-based):

1. **minimal-gpu** - GPU-enabled minimal container

   - Based on NVIDIA CUDA base images
   - Includes Java support
   - Tag format: `dbx-runtime:minimal-gpu`

2. **python-gpu** - GPU Python container

   - Extends minimal-gpu
   - CUDA-enabled Python environment
   - Runtime metadata labels
   - Tag format: `dbx-runtime:python-gpu-py{version}`

3. **dbfsfuse-gpu** - GPU DBFS FUSE container

   - Extends python-gpu
   - Tag format: `dbx-runtime:dbfsfuse-gpu-py{version}`

4. **standard-gpu** - GPU standard container
   - Extends dbfsfuse-gpu
   - Tag format: `dbx-runtime:standard-gpu-py{version}`

**Standalone**: 5. **gpu** - Standalone GPU-enabled container

- Based directly on NVIDIA CUDA images
- R environment for GPU workloads
- Runtime-specific (per LTS version)
- Separate from standard/GPU chains

### Runtime Variations

For runtime-specific images (python and gpu), the following variations are generated for each LTS runtime:

- **Base variant**: Standard Databricks runtime
- **ML variant**: Machine Learning runtime with additional ML libraries
- **OS variants**: Ubuntu 22.04 and 24.04 versions
- **Python variants**: Different Python versions (3.8, 3.9, 3.10, 3.11, 3.12)

## Generating Dockerfiles

### Using the CLI

Generate Dockerfiles for all runtimes:

```bash
poetry run dbx-container build --output-dir data
```

Generate for a specific runtime:

```bash
poetry run dbx-container build --runtime-version "14.3 LTS" --output-dir data
```

Generate for a specific image type:

```bash
poetry run dbx-container build --image-type gpu --output-dir data
```

### Directory Structure

Generated Dockerfiles are organized as follows:

```
data/
├── minimal/
│   └── latest/
│       ├── Dockerfile
│       └── runtime_metadata.json
├── minimal-gpu/
│   └── latest/
│       ├── Dockerfile
│       └── runtime_metadata.json
├── python/
│   └── latest/
│       ├── Dockerfile
│       └── runtime_metadata.json
├── python-gpu/
│   └── latest/
│       ├── Dockerfile
│       └── runtime_metadata.json
├── dbfsfuse/
│   └── latest/
│       ├── Dockerfile
│       └── runtime_metadata.json
├── dbfsfuse-gpu/
│   └── latest/
│       ├── Dockerfile
│       └── runtime_metadata.json
├── standard/
│   └── latest/
│       ├── Dockerfile
│       └── runtime_metadata.json
├── standard-gpu/
│   └── latest/
│       ├── Dockerfile
│       └── runtime_metadata.json
└── gpu/
    ├── 14.3 LTS_ubuntu2204-py310/
    │   ├── Dockerfile
    │   ├── Dockerfile.ml
    │   ├── runtime_metadata.json
    │   └── runtime_metadata.ml.json
    └── 16.4 LTS_ubuntu2404-py312/
        └── ...
```

## Building Docker Images

### Using the Build Script

Build all LTS images locally:

```bash
./scripts/build_images.sh
```

Build a specific runtime:

```bash
./scripts/build_images.sh --runtime "14.3 LTS"
```

Build a specific image type:

```bash
./scripts/build_images.sh --image-type python
```

Build without cache:

```bash
./scripts/build_images.sh --no-cache
```

Build and push to registry:

```bash
./scripts/build_images.sh --push --registry ghcr.io
```

### Manual Docker Build

Build a specific image manually:

```bash
# Build standard Python image (includes Python 3.12)
docker build -f data/python/latest/Dockerfile -t dbx-runtime:python-py312 .

# Build GPU Python image
docker build -f data/python-gpu/latest/Dockerfile -t dbx-runtime:python-gpu-py312 .

# Build GPU runtime 16.4 LTS ML variant
docker build -f data/gpu/16.4\ LTS_ubuntu2404-py312/Dockerfile.ml -t dbx-runtime-gpu:16.4-lts-ml .

# Build complete standard chain
docker build -f data/minimal/latest/Dockerfile -t dbx-runtime:minimal .
docker build -f data/python/latest/Dockerfile -t dbx-runtime:python-py312 .
docker build -f data/dbfsfuse/latest/Dockerfile -t dbx-runtime:dbfsfuse-py312 .
docker build -f data/standard/latest/Dockerfile -t dbx-runtime:standard-py312 .
```

## CI/CD Pipeline

The GitHub Actions workflow `.github/workflows/docker-build.yaml` automatically:

1. Generates Dockerfiles for all LTS runtimes
2. Builds Docker images in parallel using a matrix strategy
3. Pushes images to GitHub Container Registry (ghcr.io)

### Triggering the Pipeline

**Automatic**: On push to main branch or pull request

**Manual**: Via workflow dispatch with options:

- Runtime version filter
- Image type filter
- Push to registry toggle

### Image Tags

Images are tagged with multiple variants:

- `<image-type>:<runtime-version>` - e.g., `python:14.3-lts`
- `<image-type>:<runtime-version>-ml` - ML variant
- `<image-type>:<runtime-version>-ubuntu<version>` - OS-specific
- `<image-type>:<runtime-version>-py<version>` - Python version-specific
- `<image-type>:latest` - Most recent LTS (base variant only)

## Using the Images

### Pull from Registry

```bash
# Pull latest Python runtime
docker pull ghcr.io/<owner>/dbx-runtime-python:latest

# Pull specific LTS version
docker pull ghcr.io/<owner>/dbx-runtime-python:14.3-lts

# Pull ML variant
docker pull ghcr.io/<owner>/dbx-runtime-gpu:16.4-lts-ml
```

### Run a Container

```bash
# Run Python runtime interactively
docker run -it ghcr.io/<owner>/dbx-runtime-python:14.3-lts bash

# Run with volume mount
docker run -it -v $(pwd):/workspace ghcr.io/<owner>/dbx-runtime-python:latest bash
```

### Use in Docker Compose

```yaml
version: "3.8"

services:
  databricks-python:
    image: ghcr.io/<owner>/dbx-runtime-python:14.3-lts
    volumes:
      - ./notebooks:/databricks/notebooks
    environment:
      - PYSPARK_PYTHON=/databricks/python3/bin/python3
```

### Use as Base Image

```dockerfile
FROM ghcr.io/<owner>/dbx-runtime-python:14.3-lts

# Add your custom dependencies
RUN /databricks/python3/bin/pip install pandas scikit-learn

# Copy your application
COPY ./app /app

WORKDIR /app
CMD ["/databricks/python3/bin/python", "main.py"]
```

## Available LTS Runtimes

The following LTS runtimes are currently supported:

- **10.4 LTS** - Ubuntu 20.04, Python 3.8
- **11.3 LTS** - Ubuntu 20.04, Python 3.9
- **12.2 LTS** - Ubuntu 20.04, Python 3.9
- **13.3 LTS** - Ubuntu 22.04/24.04, Python 3.10
- **14.3 LTS** - Ubuntu 22.04/24.04, Python 3.10
- **15.4 LTS** - Ubuntu 22.04/24.04, Python 3.11
- **16.4 LTS** - Ubuntu 22.04/24.04, Python 3.12

Each LTS runtime includes:

- Base variant (standard Databricks runtime)
- ML variant (with machine learning libraries)
- Multiple OS versions (Ubuntu 22.04 and 24.04 where applicable)

## Troubleshooting

### Build Failures

If a build fails, check:

1. Dockerfile syntax and paths
2. Network connectivity for package downloads
3. Disk space availability
4. Docker daemon configuration

### Missing Dependencies

Some images require additional files:

- Python images need `src/dbx_container/data/requirements.txt`
- Python images need `src/dbx_container/data/python-lsp-requirements.txt`

Ensure these files exist before building.

### Cache Issues

Clear Docker cache if encountering stale builds:

```bash
docker builder prune
docker system prune -a
```

Or use the `--no-cache` flag:

```bash
./scripts/build_images.sh --no-cache
```

## Development

### Testing Changes

1. Modify Dockerfile templates in `src/dbx_container/images/`
2. Regenerate Dockerfiles: `poetry run dbx-container build`
3. Test build locally: `./scripts/build_images.sh --runtime "14.3 LTS" --image-type python`
4. Verify the container works: `docker run -it <image-name> bash`

### Adding New Image Types

1. Create a new class in `src/dbx_container/images/`
2. Extend `MinimalUbuntuDockerfile` or another base class
3. Add to `image_types` in `engine.py`
4. Update build scripts and CI pipeline

### Updating Runtime Versions

Runtime information is automatically scraped from Databricks documentation. To update:

```bash
poetry run dbx-container list --fetch
```

This will fetch the latest runtime information and regenerate the Dockerfiles.

## References

- [Databricks Container Services](https://docs.databricks.com/en/compute/custom-containers.html)
- [Databricks Runtime Release Notes](https://docs.databricks.com/en/release-notes/runtime/index.html)
- [Official Databricks Containers](https://github.com/databricks/containers)
