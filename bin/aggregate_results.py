#!/usr/bin/env python3
"""Aggregate per-sample tool outputs into a single results table."""

import argparse
import csv
import os
import sys

# pINV-specific genes: present on the invasion plasmid, absent/rare on chromosome
PINV_MARKERS = {
    "icsA", "virG",   # actin-based motility (pINV only)
    "virF",           # master transcriptional activator (pINV only)
    "virB",           # transcriptional activator (pINV only)
    "ipaB", "ipaC",   # translocon subunits (primarily pINV)
    "ipgD",           # inositol phosphatase effector
}


def load_mykrobe(files):
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
    results = {}
    for f in files:
        if not os.path.exists(f) or "NO_FILE" in f:
            continue
        with open(f) as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            for row in reader:
                sid  = row.get("Name", "").strip()
                gene = (row.get("Gene symbol") or row.get("Element symbol") or "").strip()
                if not sid or not gene:
                    continue
                results.setdefault(sid, set()).add(gene)
    return {sid: ";".join(sorted(genes)) if genes else "NA"
            for sid, genes in results.items()}


def load_plasmidfinder(files):
    """Return {sample_id: semicolon-list of replicons}."""
    results = {}
    for f in files:
        if not os.path.exists(f) or "NO_FILE" in f:
            continue
        sid = os.path.basename(f).replace("_plasmidfinder.tsv", "")
        replicons = set()
        with open(f) as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            for row in reader:
                plasmid = (row.get("Plasmid") or "").strip()
                if plasmid and plasmid not in ("No replicons found", "NA", ""):
                    replicons.add(plasmid)
        results[sid] = ";".join(sorted(replicons)) if replicons else "NA"
    return results


def load_abricate_vfdb(files):
    """Return {sample_id: (gene_list_str, pinv_present_str)}.
    Input format (BLAST-based pINV screen):
      sample  gene  %identity  %coverage
    pINV is considered present if any of the PINV_MARKERS are detected.
    """
    results = {}
    for f in files:
        if not os.path.exists(f) or "NO_FILE" in f:
            continue
        sid = os.path.basename(f).replace("_vfdb.tsv", "")
        genes = set()
        with open(f) as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            for row in reader:
                gene = row.get("gene", "").strip()
                if gene and gene not in ("NA", ""):
                    genes.add(gene)
        pinv = "Y" if genes else "N"
        results[sid] = (";".join(sorted(genes)) if genes else "NA", pinv)
    return results


def load_is_screen(files):
    """Return {sample_id: semicolon-list of 'IS_element(N copies)'}."""
    results = {}
    for f in files:
        if not os.path.exists(f) or "NO_FILE" in f:
            continue
        sid = os.path.basename(f).replace("_is_screen.tsv", "")
        elements = []
        with open(f) as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            for row in reader:
                is_elem = row.get("IS_element", "").strip()
                copies  = row.get("copies", "").strip()
                if is_elem and is_elem not in ("NA", ""):
                    elements.append(f"{is_elem}({copies})")
        results[sid] = ";".join(sorted(elements)) if elements else "NA"
    return results


def main():
    parser = argparse.ArgumentParser(description="Aggregate sonnei-typer results")
    parser.add_argument("--mykrobe",      nargs="+", default=[])
    parser.add_argument("--mlst",         nargs="+", default=[])
    parser.add_argument("--amrfinder",    nargs="+", default=[])
    parser.add_argument("--plasmidfinder",nargs="+", default=[])
    parser.add_argument("--abricate",     nargs="+", default=[])
    parser.add_argument("--is-screen",    nargs="+", default=[])
    parser.add_argument("--st-complexes", default=None)
    parser.add_argument("--output",       required=True)
    args = parser.parse_args()

    mykrobe     = load_mykrobe(args.mykrobe)
    mlst_raw    = load_mlst(args.mlst)
    st_lookup   = load_st_complexes(args.st_complexes)
    amrfinder   = load_amrfinder(args.amrfinder)
    plasmidfinder = load_plasmidfinder(args.plasmidfinder)
    vfdb        = load_abricate_vfdb(args.abricate)
    is_screen   = load_is_screen(getattr(args, 'is_screen', []))

    all_samples = sorted(set(
        list(mykrobe.keys()) + list(mlst_raw.keys()) +
        list(amrfinder.keys()) + list(plasmidfinder.keys())
    ))

    columns = [
        "sample",
        "mykrobe_genotype", "mykrobe_lineage", "mykrobe_clade",
        "mykrobe_subclade", "mykrobe_genotype_name", "mykrobe_confidence",
        "mlst_st", "mlst_st_complex",
        "amrfinder_genes",
        "plasmidfinder_replicons",
        "pinv_present", "virulence_genes",
        "is_elements",
    ]

    with open(args.output, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, delimiter="\t",
                                extrasaction="ignore")
        writer.writeheader()

        for sid in all_samples:
            mk  = mykrobe.get(sid, {})
            ml  = mlst_raw.get(sid, {})
            st  = ml.get("mlst_st", "NA")
            vf_genes, pinv = vfdb.get(sid, ("NA", "N"))
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
                "plasmidfinder_replicons": plasmidfinder.get(sid, "NA"),
                "pinv_present":          pinv,
                "virulence_genes":       vf_genes,
                "is_elements":           is_screen.get(sid, "NA"),
            }
            writer.writerow(row)

    print(f"Written: {args.output} ({len(all_samples)} samples)", file=sys.stderr)


if __name__ == "__main__":
    main()
