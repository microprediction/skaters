#!/bin/bash
# Compile the skaters JSS paper.
# Usage: ./compile_paper.sh

set -e

echo "Setting up JSS paper compilation..."

if ! command -v tectonic &> /dev/null; then
    echo "Tectonic not found. Install with:"
    echo "   macOS:  brew install tectonic"
    echo "   Linux:  cargo install tectonic"
    exit 1
fi

# A minimal jss.cls is vendored alongside this paper so it builds offline. If you
# want the official class, drop the real jss.cls in here (e.g. from the JSS
# template at https://www.jstatsoft.org/about/submissions) and it takes priority.
if [ ! -f "jss.cls" ]; then
    echo "ERROR: jss.cls not found (it should be vendored in this directory)." >&2
    exit 1
fi

echo "Compiling skaters-jss.tex with Tectonic..."
tectonic skaters-jss.tex

echo "Cleaning up auxiliary files..."
rm -f *.aux *.log *.bbl *.blg *.out *.toc *.lot *.lof

echo "Done: skaters-jss.pdf"
if [[ "$OSTYPE" == "darwin"* ]]; then
    open skaters-jss.pdf
fi
