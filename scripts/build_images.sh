#!/usr/bin/env bash
# Build Docker images locally for Databricks runtimes

set -euo pipefail

# Default values
RUNTIME_VERSION=""
IMAGE_TYPE="all"
PUSH=false
REGISTRY="ghcr.io"
IMAGE_PREFIX="$(git config --get remote.origin.url | sed 's/.*:\(.*\)\.git/\1/' | tr '[:upper:]' '[:lower:]')"
NO_CACHE=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --runtime)
            RUNTIME_VERSION="$2"
            shift 2
            ;;
        --image-type)
            IMAGE_TYPE="$2"
            shift 2
            ;;
        --push)
            PUSH=true
            shift
            ;;
        --registry)
            REGISTRY="$2"
            shift 2
            ;;
        --no-cache)
            NO_CACHE=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --runtime RUNTIME      Build specific runtime version (e.g., '14.3 LTS')"
            echo "  --image-type TYPE      Build specific image type (minimal|python|standard|gpu|all)"
            echo "  --push                 Push images to registry after building"
            echo "  --registry REGISTRY    Registry to push to (default: ghcr.io)"
            echo "  --no-cache            Build without cache"
            echo "  --help                 Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Generate Dockerfiles
log_info "Generating Dockerfiles..."

BUILD_CMD="poetry run dbx-container build --output-dir data"

if [ -n "$RUNTIME_VERSION" ]; then
    BUILD_CMD="$BUILD_CMD --runtime-version '$RUNTIME_VERSION'"
fi

if [ "$IMAGE_TYPE" != "all" ]; then
    BUILD_CMD="$BUILD_CMD --image-type $IMAGE_TYPE"
fi

eval "$BUILD_CMD"

if [ $? -ne 0 ]; then
    log_error "Failed to generate Dockerfiles"
    exit 1
fi

log_info "Dockerfiles generated successfully"

# Build images
log_info "Building Docker images..."

# Read build summary to get list of images to build
SUMMARY_FILE="data/build_summary.json"

if [ ! -f "$SUMMARY_FILE" ]; then
    log_error "Build summary not found: $SUMMARY_FILE"
    exit 1
fi

# Counter for built images
BUILT_COUNT=0
FAILED_COUNT=0

# Build non-runtime-specific images
for IMG_TYPE in minimal gpu; do
    if [ "$IMAGE_TYPE" != "all" ] && [ "$IMAGE_TYPE" != "$IMG_TYPE" ]; then
        continue
    fi

    DOCKERFILE="data/$IMG_TYPE/latest/Dockerfile"
    if [ ! -f "$DOCKERFILE" ]; then
        log_warn "Dockerfile not found: $DOCKERFILE"
        continue
    fi

    IMAGE_NAME="$REGISTRY/dbx-runtime-$IMG_TYPE:latest"
    log_info "Building $IMAGE_NAME..."

    BUILD_ARGS=""
    if [ "$NO_CACHE" = true ]; then
        BUILD_ARGS="--no-cache"
    fi

    if docker build $BUILD_ARGS -f "$DOCKERFILE" -t "$IMAGE_NAME" .; then
        log_info "Successfully built $IMAGE_NAME"
        ((BUILT_COUNT++))

        if [ "$PUSH" = true ]; then
            log_info "Pushing $IMAGE_NAME..."
            docker push "$IMAGE_NAME"
        fi
    else
        log_error "Failed to build $IMAGE_NAME"
        ((FAILED_COUNT++))
    fi
done

# Build runtime-specific images (python and gpu)
for RUNTIME_IMG_TYPE in python gpu; do
    if [ "$IMAGE_TYPE" != "all" ] && [ "$IMAGE_TYPE" != "$RUNTIME_IMG_TYPE" ]; then
        continue
    fi

    # Find all runtime directories
    if [ -d "data/$RUNTIME_IMG_TYPE" ]; then
        for RUNTIME_DIR in data/$RUNTIME_IMG_TYPE/*/; do
            RUNTIME_NAME=$(basename "$RUNTIME_DIR")

            # Skip non-LTS if building for production
            if [ -z "$RUNTIME_VERSION" ] && [[ ! "$RUNTIME_NAME" =~ LTS ]]; then
                log_info "Skipping non-LTS runtime: $RUNTIME_NAME"
                continue
            fi

            # Build base Dockerfile
            DOCKERFILE="$RUNTIME_DIR/Dockerfile"
            if [ -f "$DOCKERFILE" ]; then
                # Clean up runtime name for image tag
                RUNTIME_TAG=$(echo "$RUNTIME_NAME" | sed 's/ /-/g' | tr '[:upper:]' '[:lower:]')
                IMAGE_NAME="$REGISTRY/dbx-runtime-$RUNTIME_IMG_TYPE:$RUNTIME_TAG"

                log_info "Building $IMAGE_NAME..."

                BUILD_ARGS=""
                if [ "$NO_CACHE" = true ]; then
                    BUILD_ARGS="--no-cache"
                fi

                if docker build $BUILD_ARGS -f "$DOCKERFILE" -t "$IMAGE_NAME" .; then
                    log_info "Successfully built $IMAGE_NAME"
                    ((BUILT_COUNT++))

                    if [ "$PUSH" = true ]; then
                        log_info "Pushing $IMAGE_NAME..."
                        docker push "$IMAGE_NAME"
                    fi
                else
                    log_error "Failed to build $IMAGE_NAME"
                    ((FAILED_COUNT++))
                fi
            fi

            # Build ML Dockerfile if exists
            DOCKERFILE_ML="$RUNTIME_DIR/Dockerfile.ml"
            if [ -f "$DOCKERFILE_ML" ]; then
                RUNTIME_TAG=$(echo "$RUNTIME_NAME" | sed 's/ /-/g' | tr '[:upper:]' '[:lower:]')
                IMAGE_NAME="$REGISTRY/dbx-runtime-$RUNTIME_IMG_TYPE:$RUNTIME_TAG-ml"

                log_info "Building $IMAGE_NAME..."

                BUILD_ARGS=""
                if [ "$NO_CACHE" = true ]; then
                    BUILD_ARGS="--no-cache"
                fi

                if docker build $BUILD_ARGS -f "$DOCKERFILE_ML" -t "$IMAGE_NAME" .; then
                    log_info "Successfully built $IMAGE_NAME"
                    ((BUILT_COUNT++))

                    if [ "$PUSH" = true ]; then
                        log_info "Pushing $IMAGE_NAME..."
                        docker push "$IMAGE_NAME"
                    fi
                else
                    log_error "Failed to build $IMAGE_NAME"
                    ((FAILED_COUNT++))
                fi
            fi
        done
    fi
done

# Summary
log_info "Build complete!"
log_info "Successfully built: $BUILT_COUNT images"
if [ $FAILED_COUNT -gt 0 ]; then
    log_error "Failed to build: $FAILED_COUNT images"
    exit 1
fi
