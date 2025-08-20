#!/usr/bin/env bash
set -euo pipefail

if ! command -v gh &>/dev/null; then
  echo "GitHub CLI not installed" >&2
  exit 1
fi

gh issue create --title "Improve docs" --body "Add more diagrams" || true
