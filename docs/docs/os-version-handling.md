# OS Version Handling

## Overview

The DBX Container Builder automatically handles different Ubuntu OS versions when building Docker images for Databricks runtimes. This is particularly important when runtimes use older Ubuntu versions (e.g., 22.04) but you want to standardize on a newer version (e.g., 24.04).

## Default Behavior

By default, the builder **automatically upgrades** base images to Ubuntu 24.04 LTS, even when the runtime specifies an older version:

- **Runtime 15.4 LTS** uses Ubuntu 22.04
- **Builder automatically upgrades** to Ubuntu 24.04 for base images
- **Notification is displayed** during the build process

Example output:

```
INFO ✓ 🔄 Runtime 15.4 LTS uses Ubuntu 22.04, automatically upgrading base images to Ubuntu 24.04
```

## Why This Matters

When building Docker images in a dependency chain (minimal → standard → python), all images in the chain need to use compatible base images. If a Python runtime specifies Ubuntu 22.04, but the minimal and standard images use Ubuntu 24.04 by default, this could cause issues.

The builder solves this by:

1. **Detecting** OS version mismatches
2. **Notifying** the user about the upgrade
3. **Building** OS-specific base images when needed

## Explicit OS Version Configuration

You can explicitly specify which Ubuntu version to use for all base images:

```bash
# Use Ubuntu 22.04 for all base images
uv run dbx-container build --force-ubuntu-version "22.04"

# Use Ubuntu 20.04 for all base images
uv run dbx-container build --force-ubuntu-version "20.04"
```

When explicitly configured, you'll see:

```
INFO ✓ 📦 Building minimal with Ubuntu 22.04 as explicitly configured
INFO ✓ 📦 Building standard with Ubuntu 22.04 as explicitly configured
```

## Generated Directory Structure

The builder creates OS-specific directories for base images. Ubuntu 24.04 (the default/latest) is stored in the `latest/` folder, while other versions get their own specific folders:

```
data/
├── minimal/
│   ├── latest/          # Ubuntu 24.04 (default)
│   └── ubuntu2204/      # Ubuntu 22.04 specific (if needed)
├── standard/
│   ├── latest/          # Ubuntu 24.04 (default)
│   └── ubuntu2204/      # Ubuntu 22.04 specific (if needed)
└── python/
    ├── 15.4-LTS-ubuntu2204-py311/  # Uses ubuntu2204 base (if built with --force-ubuntu-version)
    ├── 16.4-LTS-ubuntu2404-py312/  # Uses latest base
    └── 17.3-LTS-ubuntu2404-py312/  # Uses latest base
```

## Build Process

### Automatic Upgrade (Default)

1. Detect runtime OS version (e.g., Ubuntu 22.04)
2. Display notification about upgrade to 24.04
3. Build OS-specific base images (minimal, standard) with Ubuntu 24.04
4. Build runtime-specific images (python) that depend on these bases

### Explicit Configuration

1. User specifies `--force-ubuntu-version "22.04"`
2. Display notification about explicit configuration
3. Build OS-specific base images with Ubuntu 22.04
4. Build runtime-specific images that depend on these bases

## Dependency Chain

The builder ensures the entire dependency chain uses consistent OS versions:

```
ubuntu:24.04 (or custom)
    ↓
minimal (or minimal-gpu)
    ↓
standard (or standard-gpu)
    ↓
python (or python-gpu)
```

## Examples

### Building with Default Behavior

```bash
# Automatically upgrades to Ubuntu 24.04
uv run dbx-container build
```

Output:

```
🔨 Building images for runtime 15.4 LTS (LTS)
INFO ✓ 🔄 Runtime generic uses Ubuntu 22.04, automatically upgrading base images to Ubuntu 24.04
INFO ✓ Generated 2/2 image types successfully
```

### Building with Explicit OS Version

```bash
# Use Ubuntu 22.04 throughout
uv run dbx-container build --force-ubuntu-version "22.04"
```

Output:

```
🔨 Building images for runtime 15.4 LTS (LTS)
INFO ✓ 📦 Building minimal with Ubuntu 22.04 as explicitly configured
INFO ✓ 📦 Building standard with Ubuntu 22.04 as explicitly configured
INFO ✓ Generated 2/2 image types successfully
```

### Building Specific Runtime

```bash
# Build only 15.4 LTS with Ubuntu 22.04
uv run dbx-container build --runtime-version "15.4 LTS" --force-ubuntu-version "22.04"
```

## Benefits

- ✅ **Automatic handling** of OS version differences
- ✅ **Clear notifications** about version upgrades
- ✅ **Flexible configuration** for custom requirements
- ✅ **Consistent dependency chains** across all images
- ✅ **No breaking changes** - works with existing builds

## Technical Details

The OS version handling is implemented in the `RuntimeContainerEngine` class:

- `should_upgrade_os_version()` - Determines if upgrade is needed
- `force_ubuntu_version` - Configuration parameter for explicit control
- OS-specific base image generation during `build_all_images_for_runtime()`

The system respects the dependency chain and ensures:

1. Base images (minimal, standard) are built with correct OS version
2. Runtime-specific images (python) reference the correct base images
3. Notifications are displayed for transparency
