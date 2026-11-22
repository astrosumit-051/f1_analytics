#!/bin/sh
# Concatenate the sections in order and export with pandoc.
set -e
cd "$(dirname "$0")"
mkdir -p build
pandoc sections/*.md --resource-path=.:sections -o build/undercut_window_report.docx
echo "wrote report/build/undercut_window_report.docx"
