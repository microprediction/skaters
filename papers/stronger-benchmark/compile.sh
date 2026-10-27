#!/bin/bash
# Compile the stronger-benchmark paper. Usage: ./compile.sh
set -e
cd "$(dirname "$0")"

if ! command -v tectonic &> /dev/null; then
    echo "Tectonic not found. Install with:"
    echo "   macOS:  brew install tectonic"
    echo "   Linux:  cargo install tectonic"
    exit 1
fi

# The numbers in the tables are typed, so check them against the store first.
PY=../../.venv/bin/python
[ -x "$PY" ] || PY=python3
"$PY" verify_paper.py

# A minimal jss.cls is vendored here so the paper builds offline.
if [ ! -f "jss.cls" ]; then
    echo "ERROR: jss.cls not found (it should be vendored in this directory)." >&2
    exit 1
fi

echo "Compiling stronger-benchmark.tex with Tectonic..."
tectonic stronger-benchmark.tex

rm -f *.aux *.log *.bbl *.blg *.out *.toc *.lot *.lof
echo "Done: stronger-benchmark.pdf"
