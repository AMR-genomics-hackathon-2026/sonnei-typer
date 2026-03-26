#!/usr/bin/env python3
"""Parse a Mykrobe sonnei JSON output file into a single-row TSV."""

import json
import sys

HEADER = "\t".join([
    "sample",
    "mykrobe_genotype",
    "mykrobe_lineage",
    "mykrobe_clade",
    "mykrobe_subclade",
    "mykrobe_genotype_name",
    "mykrobe_confidence",
])

NA_ROW_TEMPLATE = "\t".join([
    "{sample}",
    "NA", "NA", "NA", "NA", "NA", "NA",
])


def na_row(sample_id):
    return NA_ROW_TEMPLATE.format(sample=sample_id)


def clean(v):
    return str(v) if v not in (None, "", "-") else "NA"


def parse(json_path, sample_id):
    try:
        with open(json_path) as fh:
            data = json.load(fh)
    except Exception as e:
        return na_row(sample_id)

    # Error sentinel written by the shell fallback
    if "error" in data:
        return na_row(sample_id)

    # Top-level key is the sample name passed to mykrobe --sample
    sample_key = list(data.keys())[0]
    sample_data = data[sample_key]

    # ── Try new-style: phylogenetics.lineage (panel 20210201) ────────────────
    phylo = sample_data.get("phylogenetics", {})
    lineage_block = phylo.get("lineage", {})
    lineage_list = lineage_block.get("lineage", [])

    if lineage_list:
        # Take the most specific call (last item after sorting by specificity)
        calls = sorted(lineage_list, key=lambda x: x.count("."), reverse=True)
        lineage_call = calls[0]  # e.g. "lineage2.1"

        # Parse hierarchy from dotted notation: lineage2.1 → lineage=2, clade=2.1
        parts = lineage_call.replace("lineage", "").split(".")
        lineage  = f"lineage{parts[0]}" if parts else "NA"
        clade    = f"lineage{'.'.join(parts[:2])}" if len(parts) >= 2 else "NA"
        subclade = f"lineage{'.'.join(parts[:3])}" if len(parts) >= 3 else "NA"

        # Confidence: good_nodes / tree_depth if available
        calls_summary = lineage_block.get("calls_summary", {})
        summary = calls_summary.get(lineage_call, {})
        good = summary.get("good_nodes", None)
        depth = summary.get("tree_depth", None)
        confidence = f"{good}/{depth}" if good is not None and depth else "NA"

        return "\t".join([
            sample_id,
            clean(lineage_call),  # genotype = most specific call
            clean(lineage),
            clean(clade),
            clean(subclade),
            "NA",                 # no named genotype in this panel
            clean(confidence),
        ])

    # ── Fallback: old-style genotyping block ─────────────────────────────────
    geno = sample_data.get("genotyping", {})
    if geno:
        return "\t".join([
            sample_id,
            clean(geno.get("genotype")),
            clean(geno.get("lineage")),
            clean(geno.get("clade")),
            clean(geno.get("sub_clade")),
            clean(geno.get("name")),
            clean(geno.get("confidence")),
        ])

    return na_row(sample_id)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Usage: parse_mykrobe.py <mykrobe.json> <sample_id>")

    json_path = sys.argv[1]
    sample_id = sys.argv[2]

    print(HEADER)
    print(parse(json_path, sample_id))
