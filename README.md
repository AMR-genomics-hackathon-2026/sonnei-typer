# sonnei-typer

A Nextflow pipeline for comprehensive genotyping of *Shigella sonnei* genome assemblies.

Runs four tools in parallel on each assembly and aggregates the results into a single table, then optionally posts to Microreact.

| Tool | What it provides |
|---|---|
| **Mykrobe** (v0.12.2) | Hawkey 2021 Lineage/Clade/Subclade genotype |
| **mlst** (v2.23.0) | 7-locus Achtman sequence type (ST) |
| **AMRFinder Plus** (v3.12.8) | AMR and virulence genes |
| **ShigaTyper** (v2.0.5) | Serotype confirmation |

---

## Requirements

- [Nextflow](https://www.nextflow.io/) ≥ 23.10
- One of: **conda/mamba** (Mac/Linux), **Docker Desktop** (Mac/Windows), or **Singularity/Apptainer** (HPC)
- Python ≥ 3.8 (for `make_samplesheet.py`)

---

## Step 1 — Create a samplesheet

The pipeline takes a CSV samplesheet with two columns: `id` (sample name) and `fasta` (path to assembly).

### Using the helper script (recommended)

Point it at the folder containing your assemblies:

```bash
# Basic usage — filenames become sample IDs
python bin/make_samplesheet.py \
    --input /path/to/assemblies/ \
    --output samples.csv
```

```bash
# If your files are named like ERR1234567_short.fasta, strip the suffix:
python bin/make_samplesheet.py \
    --input /path/to/assemblies/ \
    --output samples.csv \
    --strip _short
```

```bash
# Multiple suffixes to strip:
python bin/make_samplesheet.py \
    --input /path/to/assemblies/ \
    --output samples.csv \
    --strip _short _assembly _contigs
```

```bash
# Only pick up .fasta files (ignore .fa, .fna etc.):
python bin/make_samplesheet.py \
    --input /path/to/assemblies/ \
    --output samples.csv \
    --pattern "*.fasta"
```

The script will print a preview and warn you if any sample IDs clash.

### Manual samplesheet

Copy `assets/samplesheet_template.csv` and fill in your paths:

```csv
id,fasta
ERR1234567,/data/assemblies/ERR1234567.fasta
ERR8901234,/data/assemblies/ERR8901234.fasta
```

---

## Step 2 — One-time setup (conda only)

If using conda (not needed for Docker/Singularity — tools are pre-configured in the images):

```bash
# Download the Mykrobe sonnei2021 genotyping panel
mykrobe panels update_metadata --panel sonnei2021

# Update the AMRFinder Plus database
amrfinder -u
```

---

## Step 3 — Run the pipeline

### Mac (conda)
```bash
nextflow run main.nf \
    -profile conda \
    --samplesheet samples.csv \
    --outdir results/
```

### Mac or Windows (Docker Desktop)
```bash
nextflow run main.nf \
    -profile docker \
    --samplesheet samples.csv \
    --outdir results/
```

### HPC — SLURM + Singularity
```bash
nextflow run main.nf \
    -profile singularity,slurm \
    --samplesheet samples.csv \
    --outdir results/ \
    -resume
```

### HPC — PBS/Torque + Singularity
```bash
nextflow run main.nf \
    -profile singularity,pbs \
    --samplesheet samples.csv \
    --outdir results/ \
    -resume
```

### With Microreact upload
```bash
# Store your token once (never put it in a script)
nextflow secrets set MICROREACT_TOKEN <your_token>

nextflow run main.nf \
    -profile conda \
    --samplesheet samples.csv \
    --outdir results/ \
    --upload_microreact true \
    --microreact_project "Ghana sonnei survey 2026"
```

The Microreact project URL will be written to `results/microreact_url.txt`.

---

## Output

```
results/
├── sonnei_typer_results.tsv     ← main aggregated table (one row per sample)
├── mykrobe/                     ← per-sample Mykrobe JSON + parsed TSV
├── mlst/                        ← per-sample mlst TSV
├── amrfinder/                   ← per-sample AMRFinder TSV
├── shigatyper/                  ← per-sample ShigaTyper TSV
├── microreact_url.txt           ← Microreact project URL (if uploaded)
└── pipeline_info/               ← Nextflow timeline and report HTML
```

### Output table columns

| Column | Source | Description |
|---|---|---|
| `sample` | — | Sample ID from samplesheet |
| `mykrobe_genotype` | Mykrobe | Full Hawkey 2021 genotype code (e.g. `3.6.1.1.2`) |
| `mykrobe_lineage` | Mykrobe | Lineage level (e.g. `3`) |
| `mykrobe_clade` | Mykrobe | Clade level (e.g. `3.6`) |
| `mykrobe_subclade` | Mykrobe | Subclade level (e.g. `3.6.1`) |
| `mykrobe_genotype_name` | Mykrobe | Human-readable name (e.g. `CipR.MSM5`) |
| `mykrobe_confidence` | Mykrobe | `strong` or `moderate` |
| `mlst_st` | mlst | 7-locus Achtman sequence type |
| `mlst_st_complex` | lookup | ST complex (from `assets/sonnei_st_complexes.tsv`) |
| `amrfinder_genes` | AMRFinder | Semicolon-delimited AMR/virulence gene list |
| `shigatyper_serotype` | ShigaTyper | Serotype confirmation |

---

## Notes

- If a tool fails for a sample, that sample still appears in the output table with `NA` for the affected columns — the run is never aborted by a single-sample failure.
- **ShigaTyper** was designed for reads; sensitivity is reduced on assemblies. For *S. sonnei*, Mykrobe is the authoritative genotype — a ShigaTyper `no_hit` does not mean the sample is not *S. sonnei*.
- The `--resume` flag (Nextflow) allows you to re-run after a failure without reprocessing completed samples.

---

## Citation

If you use this pipeline, please cite the underlying tools:

- **Mykrobe / sonnei typing**: Hawkey *et al.* (2021) *Nat Commun* 12:2684
- **mlst**: Seemann T. mlst. https://github.com/tseemann/mlst
- **AMRFinder Plus**: Feldgarden *et al.* (2021) *Sci Rep* 11:12728
- **ShigaTyper**: Wu *et al.* (2021) *mSystems* 6:e01066-20
