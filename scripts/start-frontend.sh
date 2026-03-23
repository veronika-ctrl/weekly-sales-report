#!/usr/bin/env bash
# Start the Next.js frontend with Node 22 (required by Next.js 16).
# Uses nvm + .nvmrc so the agent or any environment can start the frontend reliably.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
if [[ -s "$NVM_DIR/nvm.sh" ]]; then
  \. "$NVM_DIR/nvm.sh"
  if [[ -f "$ROOT_DIR/.nvmrc" ]]; then
    nvm use
  else
    nvm use 22
  fi
fi

cd "$ROOT_DIR/frontend"
exec npm run dev
