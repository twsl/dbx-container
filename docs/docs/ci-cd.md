# CI/CD Pipeline Guide

This guide explains the GitHub Actions CI/CD pipeline for building and publishing Databricks runtime Docker images.

## Overview

The project uses GitHub Actions to automatically:

1. Generate Dockerfiles for all LTS runtimes
2. Build Docker images in parallel
3. Push images to GitHub Container Registry (ghcr.io)
4. Tag images with appropriate version identifiers

## Workflow File

Location: `.github/workflows/docker-build.yaml`

## Triggers

### Automatic Triggers

1. **Push to main branch**: Builds and pushes all LTS images
2. **Pull request**: Builds images for validation (doesn't push)

### Manual Trigger

Use GitHub's workflow dispatch feature with these options:

- **Runtime Version**: Filter by specific runtime (e.g., "15.4 LTS")
- **Image Type**: Choose specific type or "all"
- **Push Images**: Toggle whether to push to registry

## Jobs

### 1. generate-dockerfiles

**Purpose**: Generate Dockerfiles and create build matrix

**Steps**:

- Checkout code
- Set up Python and Poetry
- Install dependencies
- Run `dbx-container build`
- Generate build matrix JSON
- Upload Dockerfiles as artifacts

**Outputs**:

- Build matrix for parallel builds
- Dockerfiles artifact

### 2. build-images

**Purpose**: Build runtime-specific images (python, gpu)

**Strategy**:

- Parallel matrix builds
- Fail-fast disabled (continue on errors)
- Builds all LTS runtimes with variations

**Steps**:

- Download Dockerfiles artifact
- Set up Docker Buildx
- Log in to container registry
- Extract metadata and tags
- Build and push image
- Use layer caching (GitHub Actions cache)

### 3. build-non-runtime-images

**Purpose**: Build non-runtime-specific images (minimal, minimal-gpu, gpu)

**Strategy**:

- Parallel builds for each image type
- Independent of runtime versions

**Steps**:

- Similar to build-images job
- Simpler tagging (only `:latest`)

## Image Tagging Strategy

### Runtime-Specific Images (python, gpu)

Multiple tags are created for flexibility:

```
ghcr.io/twsl/dbx-runtime:python-17.3-lts-ubuntu2404-py312
ghcr.io/twsl/dbx-runtime:python-17.3-lts-ml
ghcr.io/twsl/dbx-runtime:python-16.4-lts-ubuntu2404-py312
ghcr.io/twsl/dbx-runtime:python-16.4-lts-py312
ghcr.io/twsl/dbx-runtime:python-latest  (most recent LTS)
```

### Non-Runtime-Specific Images

Non-runtime-specific images are tagged with Python version:

```
ghcr.io/twsl/dbx-runtime:minimal
ghcr.io/twsl/dbx-runtime:minimal-gpu
ghcr.io/twsl/dbx-runtime:gpu
ghcr.io/twsl/dbx-runtime:python-py312
ghcr.io/twsl/dbx-runtime:python-gpu-py312
ghcr.io/twsl/dbx-runtime:standard-py312
ghcr.io/twsl/dbx-runtime:standard-gpu-py312
```

````

Single tag:

```
ghcr.io/twsl/dbx-runtime:minimal-latest
ghcr.io/twsl/dbx-runtime:gpu-latest
ghcr.io/twsl/dbx-runtime:standard-latest
```

## Build Matrix

The build matrix is dynamically generated from `build_summary.json`:

```json
{
  "include": [
    {
      "runtime": "17.3 LTS",
      "image_type": "python",
      "variant": "",
      "suffix": "-ubuntu2404-py312"
    },
    {
      "runtime": "16.4 LTS",
      "image_type": "python",
      "variant": ".ml",
      "suffix": "-ubuntu2404-py312"
    },
    ...
  ]
}
```

## Permissions

The workflow requires:

- `contents: read` - Read repository contents
- `packages: write` - Push to GitHub Container Registry

These are configured per job in the workflow file.

## Caching

The workflow uses GitHub Actions cache for:

- Docker layer cache (BuildKit)
- Significantly speeds up subsequent builds
- Shared across workflow runs

Cache keys:

- `type=gha` - GitHub Actions cache backend
- Scoped to repository and branch

## Manual Workflow Dispatch

### Via GitHub UI

1. Go to Actions tab
2. Select "Build and Push Docker Images"
3. Click "Run workflow"
4. Choose options:
   - Branch (default: main)
   - Runtime version (optional filter)
   - Image type (default: all)
   - Push images (default: false)

### Via GitHub CLI

```bash
# Build all LTS images and push
gh workflow run docker-build.yaml \
  --ref main \
  -f image_type=all \
  -f push_images=true

# Build specific runtime
gh workflow run docker-build.yaml \
  --ref main \
  -f runtime_version="15.4 LTS" \
  -f image_type=python \
  -f push_images=false
```

## Monitoring

### Check Workflow Status

```bash
# List recent workflow runs
gh run list --workflow=docker-build.yaml

# View specific run
gh run view <run-id>

# Watch a running workflow
gh run watch <run-id>
```

### View Logs

```bash
# Download logs
gh run view <run-id> --log

# Download logs for specific job
gh run view <run-id> --job=<job-id> --log
```

## Troubleshooting

### Build Failures

**Check the logs**:

1. Go to Actions tab
2. Click on the failed workflow run
3. Click on the failed job
4. Expand the failed step

**Common issues**:

- Network timeouts during package downloads
- Insufficient disk space
- Docker layer cache corruption
- Missing dependencies

**Solutions**:

- Re-run the workflow
- Clear cache and rebuild
- Check Dockerfile syntax
- Verify all required files exist

### Authentication Issues

If pushing to registry fails:

1. Check `GITHUB_TOKEN` permissions
2. Verify repository settings allow package publishing
3. Ensure workflow has `packages: write` permission

### Matrix Generation Failures

If the build matrix is empty or incorrect:

1. Check `build_summary.json` was generated correctly
2. Verify `generate_build_matrix.py` script logic
3. Review filter parameters (--only-lts, --image-type)

### Resource Limits

GitHub Actions runners have resource constraints:

- 2-core CPU
- 7 GB RAM
- 14 GB SSD disk space

Large images may hit limits. Consider:

- Optimizing Dockerfile layers
- Removing unnecessary files
- Using multi-stage builds

## Best Practices

### 1. Test Locally First

Before pushing changes that affect the CI:

```bash
# Generate Dockerfiles
poetry run dbx-container build

# Test matrix generation
python scripts/generate_build_matrix.py \
  --build-summary data/build_summary.json \
  --only-lts

# Build a sample image
./scripts/build_images.sh --runtime "15.4 LTS" --image-type python
```

### 2. Use Pull Requests

- Open PRs for changes
- Let CI validate builds
- Review build logs before merging

### 3. Version Tags

For releases:

```bash
# Tag a release
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0

# Trigger workflow for the tag
gh workflow run docker-build.yaml --ref v1.0.0
```

### 4. Monitor Disk Usage

GitHub Actions has disk space limits. The workflow includes:

```yaml
- name: Free Disk Space (Ubuntu)
  uses: jlumbroso/free-disk-space@main
```

This removes unnecessary software to free up space.

### 5. Parallel Builds

The matrix strategy builds images in parallel, but GitHub has concurrency limits:

- Free tier: 20 concurrent jobs
- Pro/Team/Enterprise: Higher limits

Plan your matrix size accordingly.

## Extending the Pipeline

### Add New Image Type

1. Update `src/dbx_container/engine.py` to include new type
2. Regenerate Dockerfiles
3. Update `generate_build_matrix.py` if needed
4. Test locally
5. Update workflow if special handling needed

### Add Quality Checks

Add additional jobs to the workflow:

```yaml
jobs:
  lint-dockerfiles:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v6
      - name: Lint Dockerfiles
        uses: hadolint/hadolint-action@v3.1.0
        with:
          dockerfile: data/**/Dockerfile*
```

### Add Security Scanning

Scan images for vulnerabilities:

```yaml
scan-images:
  needs: build-images
  runs-on: ubuntu-latest
  steps:
    - name: Run Trivy vulnerability scanner
      uses: aquasecurity/trivy-action@master
      with:
        image-ref: ${{ matrix.image }}
        format: "sarif"
        output: "trivy-results.sarif"
```

### Add Notifications

Send build notifications:

```yaml
notify:
  needs: [build-images, build-non-runtime-images]
  if: always()
  runs-on: ubuntu-latest
  steps:
    - name: Send Slack notification
      uses: 8398a7/action-slack@v3
      with:
        status: ${{ job.status }}
        webhook_url: ${{ secrets.SLACK_WEBHOOK }}
```

## Cost Optimization

GitHub Actions minutes are consumed during builds:

1. **Use caching**: Enabled by default in the workflow
2. **Optimize Dockerfiles**: Reduce build time
3. **Filter builds**: Use runtime/image type filters
4. **Self-hosted runners**: For large-scale usage

## Security Considerations

### 1. Token Permissions

Use minimal required permissions:

```yaml
permissions:
  contents: read
  packages: write
```

### 2. Secret Management

Don't hardcode secrets:

```yaml
env:
  REGISTRY: ghcr.io
  # Never: PASSWORD: my-secret-password
```

Use GitHub Secrets instead:

```yaml
password: ${{ secrets.REGISTRY_PASSWORD }}
```

### 3. Image Scanning

Consider adding:

- Vulnerability scanning
- License compliance checks
- Malware scanning

### 4. Registry Security

- Enable package security features
- Use signed images (Docker Content Trust)
- Regularly update base images

## See Also

- [Docker Build Guide](docker-build.md) - Building images locally
- [Docker Compose Guide](docker-compose.md) - Using images with Docker Compose
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [GitHub Container Registry](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry)
````
