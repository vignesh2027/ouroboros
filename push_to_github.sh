#!/usr/bin/env bash
# One-time GitHub publish for Ouroboros.
# Your gh token expired, so step 1 re-authenticates. Everything else is automatic.
set -e
cd "$(dirname "$0")"

echo "==> 1/4  Re-authenticating with GitHub"
gh auth login -h github.com -p https -w

echo "==> 2/4  Creating the repository"
gh repo create ouroboros --public --source=. --remote=origin \
  --description "Detecting self-confirming retrieval loops in agentic RAG" || true

echo "==> 3/4  Pushing"
git push -u origin main

echo "==> 4/4  Enabling GitHub Pages from the Actions workflow"
gh api -X POST repos/:owner/ouroboros/pages -f build_type=workflow 2>/dev/null \
  || echo "    (Pages may already be enabled, or enable it at Settings > Pages > Source: GitHub Actions)"

echo
echo "Done."
echo "  Repo : https://github.com/vignesh2027/ouroboros"
echo "  Pages: https://vignesh2027.github.io/ouroboros  (live in about a minute)"
