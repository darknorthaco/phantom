#!/bin/bash
# Professional package builder for Unix systems (Linux/macOS)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
VERSION_FILE="$PROJECT_ROOT/VERSION"
if [ ! -f "$VERSION_FILE" ]; then
    echo -e "${YELLOW}Warning: VERSION file not found, using default${NC}"
    VERSION="1.0.0"
else
    VERSION=$(cat "$VERSION_FILE")
fi

BUILD_DIR="$PROJECT_ROOT/build"
PACKAGE_NAME="phantom-complete-${VERSION}"
PACKAGE_DIR="$BUILD_DIR/$PACKAGE_NAME"

# Detect OS
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
else
    echo -e "${RED}Error: Unsupported OS: $OSTYPE${NC}"
    exit 1
fi

ARCH=$(uname -m)
FINAL_PACKAGE="$BUILD_DIR/${PACKAGE_NAME}-${OS}-${ARCH}.tar.gz"

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

show_banner() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║          Phantom Complete Package Builder               ║"
    echo "║              Unix Systems (Linux/macOS)                 ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo "Version: $VERSION"
    echo "OS: $OS ($ARCH)"
    echo "Output: $FINAL_PACKAGE"
    echo
}

check_requirements() {
    log_info "Checking build requirements..."

    # Check for required commands
    local required_commands=("tar" "gzip" "find" "sha256sum")
    for cmd in "${required_commands[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            log_error "Required command not found: $cmd"
            exit 1
        fi
    done

    # Check Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python 3 required"
        exit 1
    fi

    log_success "Requirements check passed"
}

create_package_structure() {
    log_info "Creating package structure..."

    # Clean previous build
    rm -rf "$PACKAGE_DIR"
    mkdir -p "$PACKAGE_DIR"

    # Create subdirectories
    mkdir -p "$PACKAGE_DIR"/{phantom_core,ui,installer,docs,governance,scripts}

    log_success "Package structure created"
}

copy_components() {
    log_info "Copying components..."

    # Copy phantom core
    if [ -d "$PROJECT_ROOT/phantom_core" ]; then
        cp -r "$PROJECT_ROOT/phantom_core"/* "$PACKAGE_DIR/phantom_core/" 2>/dev/null || true
        log_info "✓ Copied phantom_core"
    else
        log_warning "phantom_core directory not found"
    fi

    # Copy UI components
    if [ -d "$PROJECT_ROOT/ui" ]; then
        cp -r "$PROJECT_ROOT/ui"/* "$PACKAGE_DIR/ui/" 2>/dev/null || true
        log_info "✓ Copied ui"
    else
        log_warning "ui directory not found"
    fi

    # Copy installer
    if [ -d "$PROJECT_ROOT/installer" ]; then
        cp -r "$PROJECT_ROOT/installer"/* "$PACKAGE_DIR/installer/" 2>/dev/null || true
        log_info "✓ Copied installer"
    else
        log_warning "installer directory not found"
    fi

    # Copy docs
    if [ -d "$PROJECT_ROOT/docs" ]; then
        cp -r "$PROJECT_ROOT/docs"/* "$PACKAGE_DIR/docs/" 2>/dev/null || true
        log_info "✓ Copied docs"
    fi

    # Copy governance
    if [ -d "$PROJECT_ROOT/governance" ]; then
        cp -r "$PROJECT_ROOT/governance"/* "$PACKAGE_DIR/governance/" 2>/dev/null || true
        log_info "✓ Copied governance"
    fi

    # Copy package scripts
    cp "$SCRIPT_DIR/install.sh" "$PACKAGE_DIR/" 2>/dev/null || log_warning "install.sh not found"
    cp "$SCRIPT_DIR/uninstall.sh" "$PACKAGE_DIR/" 2>/dev/null || log_warning "uninstall.sh not found"

    log_success "Components copied"
}

generate_metadata() {
    log_info "Generating package metadata..."

    # Create VERSION file
    echo "$VERSION" > "$PACKAGE_DIR/VERSION"

    # Create BUILD_INFO
    cat > "$PACKAGE_DIR/BUILD_INFO" << EOF
Phantom Complete Package
Version: $VERSION
Built: $(date -u '+%Y-%m-%d %H:%M:%S UTC')
OS: $OS
Architecture: $ARCH
Builder: $(whoami)@$(hostname)
EOF

    # Create README for package
    cat > "$PACKAGE_DIR/README.md" << EOF
# Phantom Distributed Computing Platform

Version: $VERSION
Built for: $OS ($ARCH)

## Quick Start

1. Extract: \`tar -xzf $PACKAGE_NAME-$OS-$ARCH.tar.gz\`
2. Install: \`cd $PACKAGE_NAME && sudo bash install.sh\`
3. Start: Access the web UI at http://localhost:8080

## Documentation

See docs/ directory for complete documentation.

## Uninstall

Run: \`sudo bash uninstall.sh\`

## Support

- Documentation: docs/
- Issues: [GitHub Issues]
- Commercial: governance/COMMERCIAL.md
EOF

    log_success "Metadata generated"
}

generate_checksums() {
    log_info "Generating checksums..."

    cd "$PACKAGE_DIR"
    find . -type f -not -name "CHECKSUMS.sha256" -exec sha256sum {} \; | sort > CHECKSUMS.sha256
    cd - > /dev/null

    log_success "Checksums generated"
}

create_archive() {
    log_info "Creating archive..."

    mkdir -p "$BUILD_DIR"

    cd "$BUILD_DIR"
    tar -czf "$FINAL_PACKAGE" "$PACKAGE_NAME"

    # Verify archive
    if [ -f "$FINAL_PACKAGE" ]; then
        SIZE=$(du -h "$FINAL_PACKAGE" | cut -f1)
        log_success "Archive created: $FINAL_PACKAGE ($SIZE)"
    else
        log_error "Failed to create archive"
        exit 1
    fi
}

verify_package() {
    log_info "Verifying package..."

    # Extract to temporary location for verification
    local temp_dir=$(mktemp -d)
    tar -xzf "$FINAL_PACKAGE" -C "$temp_dir"

    # Check for required files
    local required_files=(
        "phantom_core"
        "ui"
        "installer"
        "docs"
        "VERSION"
        "BUILD_INFO"
        "README.md"
        "install.sh"
        "uninstall.sh"
    )

    local missing_files=()
    for file in "${required_files[@]}"; do
        if [ ! -e "$temp_dir/$PACKAGE_NAME/$file" ]; then
            missing_files+=("$file")
        fi
    done

    # Cleanup
    rm -rf "$temp_dir"

    if [ ${#missing_files[@]} -gt 0 ]; then
        log_error "Missing files in package: ${missing_files[*]}"
        exit 1
    fi

    log_success "Package verification passed"
}

main() {
    show_banner
    check_requirements
    create_package_structure
    copy_components
    generate_metadata
    generate_checksums
    create_archive
    verify_package

    echo
    echo -e "${GREEN}🎉 Build completed successfully!${NC}"
    echo
    echo "Package: $FINAL_PACKAGE"
    echo "Size: $(du -h "$FINAL_PACKAGE" | cut -f1)"
    echo "SHA256: $(sha256sum "$FINAL_PACKAGE" | cut -d' ' -f1)"
    echo
    echo "Next steps:"
    echo "1. Test installation: cd build && tar -xzf ${PACKAGE_NAME}-${OS}-${ARCH}.tar.gz"
    echo "2. Run: cd ${PACKAGE_NAME} && sudo bash install.sh"
    echo "3. Verify: Access http://localhost:8080"
}

# Run main function
main "$@"