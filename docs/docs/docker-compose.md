# Docker Compose Usage Guide

This guide explains how to use Docker Compose to run Databricks runtime containers locally.

## Prerequisites

- Docker Engine 20.10 or later
- Docker Compose 2.0 or later
- For GPU containers: NVIDIA Docker runtime

## Quick Start

### 1. Generate Dockerfiles

First, generate the Dockerfiles for all runtimes:

```bash
uv run dbx-container build --output-dir data
```

### 2. Start a Container

Use Docker Compose profiles to start specific containers:

```bash
# Start latest Python runtime (17.3 LTS)
docker compose --profile python up -d python-latest

# Start Python 15.4 LTS runtime
docker compose --profile python-15 up -d python-15-4

# Start latest GPU runtime (requires NVIDIA GPU)
docker compose --profile gpu up -d gpu-latest

# Start ML variant
docker compose --profile ml up -d python-ml-latest
```

### 3. Access the Container

```bash
# Execute commands in the container
docker compose exec python-latest bash

# Run Python
docker compose exec python-latest /databricks/python3/bin/python

# Run a script
docker compose exec python-latest /databricks/python3/bin/python /databricks/notebooks/my_script.py
```

### 4. Stop the Container

```bash
# Stop and remove
docker compose --profile python down

# Stop all
docker compose down
```

## Available Profiles

| Profile     | Description              | Container                       |
| ----------- | ------------------------ | ------------------------------- |
| `minimal`   | Minimal Ubuntu with Java | minimal                         |
| `python`    | All Python runtimes      | python-latest, python-15-4      |
| `python-15` | Python 15.4 LTS          | python-15-4                     |
| `python-16` | Python 16.4 LTS          | python-16-4                     |
| `python-17` | Python 17.3 LTS          | python-17-3                     |
| `python-ml` | Python ML runtimes       | python-ml-latest                |
| `gpu`       | GPU runtimes             | gpu-latest                      |
| `gpu-ml`    | GPU ML runtimes          | gpu-ml-latest                   |
| `ml`        | All ML runtimes          | python-ml-latest, gpu-ml-latest |
| `latest`    | Latest LTS runtimes      | python-latest, gpu-latest       |
| `standard`  | SSH server support       | standard                        |

## Examples

### Running Python Code

Create a notebook or script in the `notebooks/` directory:

```python
# notebooks/hello.py
print("Hello from Databricks runtime!")

import sys
print(f"Python version: {sys.version}")
```

Run it:

```bash
docker compose --profile python up -d python-latest
docker compose exec python-latest /databricks/python3/bin/python /databricks/notebooks/hello.py
```

### Using PySpark

```bash
docker compose --profile python up -d python-latest
docker compose exec python-latest bash

# Inside the container
/databricks/python3/bin/python
>>> from pyspark.sql import SparkSession
>>> spark = SparkSession.builder.appName("test").getOrCreate()
>>> df = spark.range(10)
>>> df.show()
```

### GPU-Enabled Containers

For GPU containers, ensure you have:

1. NVIDIA GPU drivers installed
2. NVIDIA Container Toolkit installed
3. Docker configured to use the NVIDIA runtime

```bash
# Test GPU access
docker compose --profile gpu up -d gpu-latest
docker compose exec gpu-latest nvidia-smi
```

### ML Workloads

ML containers include additional libraries:

```bash
docker compose --profile ml up -d python-ml-latest
docker compose exec python-ml-latest /databricks/python3/bin/python

# Inside Python
>>> import tensorflow as tf
>>> import torch
>>> import numpy as np
```

### SSH Access

The standard container includes SSH server:

```bash
docker compose --profile standard up -d standard

# SSH is available on port 2222
ssh user@localhost -p 2222
```

## Volume Mounts

By default, the following directories are mounted:

- `./notebooks` → `/databricks/notebooks` - Your Python scripts and notebooks
- `./data` → `/databricks/data` - Data files

You can modify these in `docker-compose.yml` or add additional mounts.

## Building Custom Images

### Extend a Base Image

Create a custom Dockerfile:

```dockerfile
# Dockerfile.custom
FROM dbx-runtime:python-17.3-lts-ubuntu2404-py312

# Install additional packages
RUN /databricks/python3/bin/pip install \
    mlflow \
    great_expectations \
    dbt-core

# Copy your application
COPY ./app /app
WORKDIR /app
```

Add to `docker-compose.yml`:

```yaml
services:
  custom-python:
    build:
      context: .
      dockerfile: Dockerfile.custom
    image: dbx-runtime:python-custom
    volumes:
      - ./notebooks:/databricks/notebooks
    command: tail -f /dev/null
    profiles:
      - custom
```

Build and run:

```bash
docker compose --profile custom build custom-python
docker compose --profile custom up -d custom-python
```

## Environment Variables

Common environment variables:

| Variable                 | Description                    | Default                           |
| ------------------------ | ------------------------------ | --------------------------------- |
| `PYSPARK_PYTHON`         | Python interpreter for PySpark | `/databricks/python3/bin/python3` |
| `NVIDIA_VISIBLE_DEVICES` | GPU devices to expose          | `all`                             |
| `JAVA_HOME`              | Java installation path         | `/usr/lib/jvm/zulu17-ca-amd64`    |

Set in `docker-compose.yml`:

```yaml
services:
  python-latest:
    environment:
      - PYSPARK_PYTHON=/databricks/python3/bin/python3
      - SPARK_HOME=/databricks/spark
      - MY_CUSTOM_VAR=value
```

## Troubleshooting

### Container won't start

Check logs:

```bash
docker compose --profile python logs python-latest
```

### Permission issues

Some containers may need specific user permissions:

```bash
docker compose exec --user root python-latest chown -R $(id -u):$(id -g) /databricks/notebooks
```

### Network issues

Check container networking:

```bash
docker compose exec python-latest ping -c 3 google.com
```

### Build failures

Rebuild from scratch:

```bash
docker compose --profile python build --no-cache python-latest
```

## Multiple Containers

Run multiple runtimes simultaneously:

```bash
# Start both Python and GPU containers
docker compose --profile python --profile gpu up -d

# List running containers
docker compose ps

# Access different containers
docker compose exec python-latest bash
docker compose exec gpu-latest bash
```

## Cleanup

Remove containers and volumes:

```bash
# Stop and remove containers
docker compose down

# Remove volumes as well
docker compose down -v

# Remove all images
docker compose down --rmi all
```

## Production Usage

For production deployments:

1. Use pre-built images from a registry instead of building locally
2. Configure resource limits
3. Set up health checks
4. Use secrets management
5. Configure logging drivers

Example production configuration:

```yaml
services:
  python-prod:
    image: ghcr.io/twsl/dbx-runtime:python-17.3-lts-ubuntu2404-py312
    deploy:
      resources:
        limits:
          cpus: "4"
          memory: 8G
        reservations:
          cpus: "2"
          memory: 4G
    healthcheck:
      test: ["CMD", "python", "--version"]
      interval: 30s
      timeout: 10s
      retries: 3
    logging:
      driver: json-file
      options:
        max-size: "10m"
        max-file: "3"
    restart: unless-stopped
```

## See Also

- [Docker Build Guide](docker-build.md) - Building images from scratch
- [Databricks Documentation](https://docs.databricks.com) - Official Databricks docs
- [Docker Compose Documentation](https://docs.docker.com/compose/) - Docker Compose reference
