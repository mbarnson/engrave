#!/usr/bin/env bash
# Bump version across all project files and create a git tag.
# Usage: ./scripts/bump-version.sh <new-version>
# Example: ./scripts/bump-version.sh 0.2.0

set -euo pipefail

if [ $# -ne 1 ]; then
    echo "Usage: $0 <new-version>"
    echo "Example: $0 0.2.0"
    exit 1
fi

NEW_VERSION="$1"

# Validate version format (semver without v prefix)
if ! echo "$NEW_VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+(-[a-zA-Z0-9.]+)?$'; then
    echo "Error: Version must be semver format (e.g., 0.2.0 or 0.2.0-alpha)"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "Bumping version to $NEW_VERSION..."

# 1. pyproject.toml
sed -i.bak "s/^version = \".*\"/version = \"$NEW_VERSION\"/" "$ROOT_DIR/pyproject.toml"
rm -f "$ROOT_DIR/pyproject.toml.bak"
echo "  Updated pyproject.toml"

# 2. desktop/package.json
sed -i.bak "s/\"version\": \".*\"/\"version\": \"$NEW_VERSION\"/" "$ROOT_DIR/desktop/package.json"
rm -f "$ROOT_DIR/desktop/package.json.bak"
echo "  Updated desktop/package.json"

# 3. desktop/src-tauri/tauri.conf.json
sed -i.bak "s/\"version\": \".*\"/\"version\": \"$NEW_VERSION\"/" "$ROOT_DIR/desktop/src-tauri/tauri.conf.json"
rm -f "$ROOT_DIR/desktop/src-tauri/tauri.conf.json.bak"
echo "  Updated desktop/src-tauri/tauri.conf.json"

# 4. desktop/src-tauri/Cargo.toml
sed -i.bak "s/^version = \".*\"/version = \"$NEW_VERSION\"/" "$ROOT_DIR/desktop/src-tauri/Cargo.toml"
rm -f "$ROOT_DIR/desktop/src-tauri/Cargo.toml.bak"
echo "  Updated desktop/src-tauri/Cargo.toml"

echo ""
echo "Version bumped to $NEW_VERSION in all files."
echo ""
echo "Next steps:"
echo "  git add -A"
echo "  git commit -m \"chore: bump version to v$NEW_VERSION\""
echo "  git tag v$NEW_VERSION"
echo "  git push origin main --tags"
