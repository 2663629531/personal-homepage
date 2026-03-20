#!/bin/zsh
set -euo pipefail

ROOT="/Users/xudafu/Documents/Obsidian Vault/00个人主页"

cd "$ROOT"

python3 scripts/build_diary.py

git add diary/index.json diary/posts diary/entries

if git diff --cached --quiet; then
  echo "No diary changes to publish."
  exit 0
fi

git commit -m "Update diary $(date '+%Y-%m-%d %H:%M')"
git push
