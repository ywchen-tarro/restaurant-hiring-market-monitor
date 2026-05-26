#!/bin/bash
# Run the full pytest suite.
# Tests are HTML-fixture-driven — no network calls.
set -e
cd "$(dirname "$0")"
exec python3 -m pytest tests/ "$@"
