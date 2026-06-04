#!/bin/bash
# Install project git hooks. Run once after cloning.
set -e

HOOKS_DIR="$(git rev-parse --show-toplevel)/.git/hooks"
SOURCE_DIR="$(git rev-parse --show-toplevel)/hooks"

cp "$SOURCE_DIR/pre-push" "$HOOKS_DIR/pre-push"
chmod +x "$HOOKS_DIR/pre-push"

echo "Hooks installed:"
echo "  pre-push -> .git/hooks/pre-push"
