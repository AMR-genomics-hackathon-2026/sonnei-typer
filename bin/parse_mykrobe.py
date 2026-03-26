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
    "mykrobe_status",
])

NA_ROW_TEMPLATE = "\t".join([
    "{sample}",
    "NA", "NA", "NA", "NA", "NA", "NA",
    "{status}",
])


def na_row(sample_id, status="no_data"):
    return NA_ROW_TEMPLATE.format(sample=sample_id, status=status)


def parse(json_path, sample_id):
    try:
        with open(json_path) as fh:
            data = json.load(fh)
    except Exception as e:
        return na_row(sample_id, f"json_parse_error:{e}")

    # Handle error sentinel written by the shell fallback
    if "error" in data:
        return na_row(sample_id, data["error"])

    # The top-level key is the sample name passed to mykrobe --sample
    sample_key = list(data.keys())[0]
    sample_data = data[sample_key]

    # Navigate to genotyping block
    geno = sample_data.get("genotyping", {})
    if not geno:
        # Older Mykrobe versions use a different key structure
        geno = {}

    genotype       = geno.get("genotype",    "NA")
    lineage        = geno.get("lineage",     "NA")
    clade          = geno.get("clade",       "NA")
    subclade       = geno.get("sub_clade",   "NA")
    genotype_name  = geno.get("name",        "NA")
    confidence     = geno.get("confidence",  "NA")

    # Replace None / empty strings with NA
    def clean(v):
        return v if v not in (None, "", "-") else "NA"

    row = "\t".join([
        sample_id,
        clean(genotype),
        clean(lineage),
        clean(clade),
        clean(subclade),
        clean(genotype_name),
        clean(confidence),
        "ok",
    ])
    return row


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("Usage: parse_mykrobe.py <mykrobe.json> <sample_id>")

    json_path  = sys.argv[1]
    sample_id  = sys.argv[2]

    print(HEADER)
    print(parse(json_path, sample_id))
