#!/usr/bin/env python3
"""Generate a sonnei-typer samplesheet from a folder of FASTA assemblies.

Usage
-----
  make_samplesheet.py --input /path/to/assemblies/ --output samples.csv
  make_samplesheet.py --input /path/to/assemblies/ --output samples.csv --strip _short
  make_samplesheet.py --input /path/to/assemblies/ --output samples.csv --strip _assembly _contigs

The sample ID is derived from the filename by removing the file extension
and any optional suffix strings you specify with --strip.

Example
-------
  Filename:  ERR1234567_short.fasta
  --strip _short
  ID:        ERR1234567

  Filename:  sample_001_assembly.fa
  --strip _assembly
  ID:        sample_001
"""

import argparse
import csv
import os
import sys

FASTA_EXTENSIONS = {".fasta", ".fa", ".fna", ".fas", ".fsa"}


def get_sample_id(filename, strip_suffixes):
    """Derive a clean sample ID from a filename."""
    name = filename
    # Remove FASTA extension
    for ext in FASTA_EXTENSIONS:
        if name.lower().endswith(ext):
            name = name[: -len(ext)]
            break
    # Remove any user-specified suffixes (in order given)
    for suffix in strip_suffixes:
        if name.endswith(suffix):
            name = name[: -len(suffix)]
    return name


def main():
    parser = argparse.ArgumentParser(
        description="Generate a sonnei-typer samplesheet from a FASTA folder",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--input", "-i", required=True,
        help="Folder containing FASTA assembly files"
    )
    parser.add_argument(
        "--output", "-o", required=True,
        help="Output samplesheet CSV path (e.g. samples.csv)"
    )
    parser.add_argument(
        "--strip", nargs="+", default=[],
        metavar="SUFFIX",
        help="One or more filename suffixes to strip when making the sample ID "
             "(e.g. --strip _short _assembly)"
    )
    parser.add_argument(
        "--pattern", default=None,
        metavar="GLOB",
        help="Optional glob pattern to filter files within the folder "
             "(e.g. '*.fasta'). By default all FASTA extensions are included."
    )
    args = parser.parse_args()

    folder = os.path.abspath(args.input)
    if not os.path.isdir(folder):
        sys.exit(f"ERROR: Input folder not found: {folder}")

    # Collect FASTA files
    if args.pattern:
        import fnmatch
        all_files = [f for f in os.listdir(folder)
                     if fnmatch.fnmatch(f, args.pattern)]
    else:
        all_files = [f for f in os.listdir(folder)
                     if os.path.splitext(f)[1].lower() in FASTA_EXTENSIONS]

    if not all_files:
        sys.exit(f"ERROR: No FASTA files found in {folder}. "
                 f"Expected extensions: {', '.join(sorted(FASTA_EXTENSIONS))}")

    all_files.sort()

    # Build rows and check for duplicate IDs
    rows = []
    seen_ids = {}
    for fname in all_files:
        fpath = os.path.join(folder, fname)
        sid   = get_sample_id(fname, args.strip)
        if sid in seen_ids:
            sys.exit(
                f"ERROR: Duplicate sample ID '{sid}' derived from:\n"
                f"  {seen_ids[sid]}\n"
                f"  {fpath}\n"
                f"Use --strip to remove filename suffixes that differ between files."
            )
        seen_ids[sid] = fpath
        rows.append({"id": sid, "fasta": fpath})

    # Write samplesheet
    with open(args.output, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["id", "fasta"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"Written: {args.output} ({len(rows)} samples)")
    print(f"First few entries:")
    for row in rows[:3]:
        print(f"  {row['id']}  →  {row['fasta']}")
    if len(rows) > 3:
        print(f"  ... and {len(rows) - 3} more")


if __name__ == "__main__":
    main()
