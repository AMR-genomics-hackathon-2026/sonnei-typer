#!/usr/bin/env python3
"""Aggregate per-sample tool outputs into a single results table."""

import argparse
import csv
import os
import sys


def load_mykrobe(files):
    """Return {sample_id: {col: val}} from parsed mykrobe TSVs."""
    results = {}
    for f in files:
        if not os.path.exists(f) or "NO_FILE" in f:
            continue
        with open(f) as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            for row in reader:
                sid = row["sample"]
                results[sid] = {
                    "mykrobe_genotype":      row.get("mykrobe_genotype",      "NA"),
                    "mykrobe_lineage":       row.get("mykrobe_lineage",       "NA"),
                    "mykrobe_clade":         row.get("mykrobe_clade",         "NA"),
                    "mykrobe_subclade":      row.get("mykrobe_subclade",      "NA"),
                    "mykrobe_genotype_name": row.get("mykrobe_genotype_name", "NA"),
                    "mykrobe_confidence":    row.get("mykrobe_confidence",    "NA"),
                }
    return results


def load_mlst(files):
    """Return {sample_id: st_string} from mlst TSVs.
    mlst output columns: FILE  SCHEME  ST  gene1  gene2 ...
    """
    results = {}
    for f in files:
        if not os.path.exists(f) or "NO_FILE" in f:
            continue
        with open(f) as fh:
            for line in fh:
                parts = line.strip().split("\t")
                if len(parts) < 3:
                    continue
                sid = parts[0]
                st  = parts[2] if parts[2] not in ("", "-") else "NA"
                results[sid] = {"mlst_st": st}
    return results


def load_st_complexes(f):
    """Return {st_string: st_complex} from sonnei_st_complexes.tsv."""
    lookup = {}
    if not f or not os.path.exists(f) or "NO_FILE" in f:
        return lookup
    with open(f) as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            st = row.get("st", "").strip()
            cx = row.get("st_complex", "").strip()
            if st:
                lookup[st] = cx if cx else "NA"
    return lookup


def load_amrfinder(files):
    """Return {sample_id: semicolon-delimited gene list} from AMRFinder TSVs."""
    results = {}
    for f in files:
        if not os.path.exists(f) or "NO_FILE" in f:
            continue
        with open(f) as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            for row in reader:
                # AMRFinder uses 'Name' column for the sample name when --name is set
                sid  = row.get("Name", "").strip()
                gene = row.get("Gene symbol", "").strip()
                if not sid or not gene:
                    continue
                results.setdefault(sid, set()).add(gene)
    return {sid: ";".join(sorted(genes)) if genes else "NA"
            for sid, genes in results.items()}


def load_shigatyper(files):
    """Return {sample_id: serotype_call} from ShigaTyper TSVs.
    Take the Hit with the highest % covered; fallback to 'no_hit'.
    """
    results = {}
    for f in files:
        if not os.path.exists(f) or "NO_FILE" in f:
            continue
        with open(f) as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            best = {}   # {sample_id: (pct_covered, hit)}
            for row in reader:
                sid = row.get("sample", "").strip()
                hit = row.get("Hit", "NA").strip()
                try:
                    pct = float(row.get("% covered", 0) or 0)
                except ValueError:
                    pct = 0.0
                if hit in ("NA", "", "tool_failed"):
                    results.setdefault(sid, "no_hit")
                    continue
                if sid not in best or pct > best[sid][0]:
                    best[sid] = (pct, hit)
            for sid, (_, hit) in best.items():
                results[sid] = hit
    return results


def main():
    parser = argparse.ArgumentParser(description="Aggregate sonnei-typer results")
    parser.add_argument("--mykrobe",     nargs="+", default=[])
    parser.add_argument("--mlst",        nargs="+", default=[])
    parser.add_argument("--amrfinder",   nargs="+", default=[])
    parser.add_argument("--shigatyper",  nargs="+", default=[])
    parser.add_argument("--st-complexes", default=None)
    parser.add_argument("--output",      required=True)
    args = parser.parse_args()

    mykrobe    = load_mykrobe(args.mykrobe)
    mlst_raw   = load_mlst(args.mlst)
    st_lookup  = load_st_complexes(args.st_complexes)
    amrfinder  = load_amrfinder(args.amrfinder)
    shigatyper = load_shigatyper(args.shigatyper)

    # Collect all sample IDs seen across any tool
    all_samples = sorted(set(
        list(mykrobe.keys()) +
        list(mlst_raw.keys()) +
        list(amrfinder.keys()) +
        list(shigatyper.keys())
    ))

    columns = [
        "sample",
        "mykrobe_genotype",
        "mykrobe_lineage",
        "mykrobe_clade",
        "mykrobe_subclade",
        "mykrobe_genotype_name",
        "mykrobe_confidence",
        "mlst_st",
        "mlst_st_complex",
        "amrfinder_genes",
        "shigatyper_serotype",
    ]

    with open(args.output, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, delimiter="\t",
                                extrasaction="ignore")
        writer.writeheader()

        for sid in all_samples:
            mk  = mykrobe.get(sid, {})
            ml  = mlst_raw.get(sid, {})
            st  = ml.get("mlst_st", "NA")
            row = {
                "sample":                sid,
                "mykrobe_genotype":      mk.get("mykrobe_genotype",      "NA"),
                "mykrobe_lineage":       mk.get("mykrobe_lineage",        "NA"),
                "mykrobe_clade":         mk.get("mykrobe_clade",          "NA"),
                "mykrobe_subclade":      mk.get("mykrobe_subclade",       "NA"),
                "mykrobe_genotype_name": mk.get("mykrobe_genotype_name",  "NA"),
                "mykrobe_confidence":    mk.get("mykrobe_confidence",     "NA"),
                "mlst_st":               st,
                "mlst_st_complex":       st_lookup.get(st, "NA"),
                "amrfinder_genes":       amrfinder.get(sid, "NA"),
                "shigatyper_serotype":   shigatyper.get(sid, "NA"),
            }
            writer.writerow(row)

    print(f"Written: {args.output} ({len(all_samples)} samples)", file=sys.stderr)


if __name__ == "__main__":
    main()
