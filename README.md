# sonnei-typer

A Nextflow pipeline for comprehensive genotyping of *Shigella sonnei* genome assemblies.

Runs a species gate followed by seven typing tools and aggregates the results into a single table, then optionally posts to Microreact.

| Step | Tool | What it provides |
|---|---|---|
| 1 | **Mash** (v2.3) | Species confirmation — non-*S. sonnei* samples are rejected before typing |
| 2 | **Mykrobe** (v0.13.0) | Hawkey 2021 Lineage/Clade/Subclade genotype (panel 20210201) |
| 2 | **mlst** (v2.23.0) | 7-locus Achtman sequence type (ST) |
| 2 | **AMRFinder Plus** (v3.12.8) | AMR and virulence genes |
| 2 | **PlasmidFinder** (v2.1.6) | Plasmid replicon typing |
| 2 | **pINV screen** (BLAST) | Virulence plasmid (pINV) detection via marker genes |
| 2 | **IS element screen** (BLAST) | IS element profiling (IS1, IS1A, IS30, IS600, IS186, IS629) |

Typing tools (step 2) run in parallel on confirmed *S. sonnei* assemblies only.

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
# Download the Mykrobe sonnei genotyping panel
mykrobe panels update_metadata --panel 20210201

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

## Species gate

The first step runs **Mash** to estimate the closest species match from a bundled reference sketch (`assets/sonnei_species_refs.msh`). The sketch includes five reference genomes:

| Species | Reference |
|---|---|
| *Shigella sonnei* | NC_016822.1 |
| *Shigella flexneri* | AE014073.1 |
| *Shigella boydii* | CP000036.1 |
| *Shigella dysenteriae* | AE006468.2 |
| *Escherichia coli* K-12 | NC_000913.3 |

Samples with Mash distance ≥ 0.05 from *S. sonnei*, or that match a different species more closely, are written to the Nextflow log as warnings and skipped — they do not appear in the results table.

---

## Output

```
results/
├── sonnei_typer_results.tsv     ← main aggregated table (one row per sample)
├── species_check/               ← per-sample Mash species result
├── mykrobe/                     ← per-sample Mykrobe JSON + parsed TSV
├── mlst/                        ← per-sample mlst TSV
├── amrfinder/                   ← per-sample AMRFinder TSV
├── plasmidfinder/               ← per-sample PlasmidFinder TSV
├── abricate_vfdb/               ← per-sample pINV screen TSV
├── is_screen/                   ← per-sample IS element screen TSV
├── microreact_url.txt           ← Microreact project URL (if uploaded)
└── pipeline_info/               ← Nextflow timeline and report HTML
```

### Output table columns

| Column | Source | Description |
|---|---|---|
| `sample` | — | Sample ID from samplesheet |
| `mykrobe_genotype` | Mykrobe | Hawkey 2021 genotype (e.g. `lineage2.1`) |
| `mykrobe_lineage` | Mykrobe | Lineage level (e.g. `lineage2`) |
| `mykrobe_clade` | Mykrobe | Clade level (e.g. `lineage2.1`) |
| `mykrobe_subclade` | Mykrobe | Subclade level (e.g. `lineage2.1.1`) |
| `mykrobe_genotype_name` | Mykrobe | Human-readable genotype name where assigned |
| `mykrobe_confidence` | Mykrobe | `good_nodes/tree_depth` from Mykrobe calls summary |
| `mlst_st` | mlst | 7-locus Achtman sequence type |
| `mlst_st_complex` | lookup | ST complex (from `assets/sonnei_st_complexes.tsv`) |
| `amrfinder_genes` | AMRFinder | Semicolon-delimited AMR/virulence gene list |
| `plasmidfinder_replicons` | PlasmidFinder | Semicolon-delimited plasmid replicon list |
| `pinv_present` | pINV screen | `Y` if any pINV marker gene detected, otherwise `N` |
| `virulence_genes` | pINV screen | Semicolon-delimited list of detected pINV marker genes |
| `is_elements` | IS screen | IS elements detected with copy counts, e.g. `IS1(1);IS30(2)` |

### pINV marker genes

The pINV screen queries assemblies against the following genes known to be specific to the *S. sonnei* invasion plasmid (pINV, ~214 kb):

| Gene | Function |
|---|---|
| `icsA` / `virG` | Actin-based intracellular motility |
| `virF` | Master transcriptional activator of virulence genes |
| `virB` | Transcriptional activator |
| `ipaB` | Type III secretion translocon subunit |
| `ipaC` | Type III secretion translocon subunit |
| `ipaD` | Type III secretion tip complex |

> **Note:** The pINV plasmid is not retained in all culture collection or reference strains. A result of `N` in chromosome-only assemblies does not indicate avirulence — plasmid carriage should be confirmed in fresh clinical isolates.

---

## Notes

- If a tool fails for a sample, that sample still appears in the output table with `NA` for the affected columns — the run is never aborted by a single-sample failure.
- Samples that fail the species gate are logged as warnings and excluded from the results table entirely.
- The `--resume` flag (Nextflow) allows you to re-run after a failure without reprocessing completed samples.

---

## Test and example output

Full per-tool output files are provided in [`test/example_output/`](test/example_output/).

The five test assemblies are publicly available *S. sonnei* reference or surveillance strains downloaded from NCBI. The aggregated results table is reproduced below.

| sample | mykrobe_genotype | mykrobe_lineage | mykrobe_clade | mykrobe_confidence | mlst_st | mlst_st_complex | amrfinder_genes | plasmidfinder_replicons | pinv_present | virulence_genes | is_elements |
|---|---|---|---|---|---|---|---|---|---|---|---|
| AR_0030 | lineage2.1 | lineage2 | lineage2.1 | 2/2 | 5479 | NA | acrF;blaEC;blaTEM-1;emrD;emrE;espX1;ipaH3;ipaHa;ipaHb;ipaHd;ipaHe;iucA;iucB;iucC;iucD;iutA;senB;sigA | NA | N | NA | IS1(1);IS30(1);IS600(1) |
| AR_0426 | lineage2.1 | lineage2 | lineage2.1 | 2/2 | 5479 | NA | acrF;blaEC;emrD;emrE;espX1;ipaH3;ipaHa;ipaHb;ipaHd;ipaHe;iucA;iucB;iucC;iucD;iutA;senB;sigA | NA | N | NA | IS1(1);IS30(1);IS600(1) |
| ATCC_29930 | lineage2.6 | lineage2 | lineage2.6 | 2/2 | 152 | ST152 Cplx | acrF;blaEC;emrD;emrE;espX1;ipaH3;ipaHa;ipaHb;ipaHd;ipaHe;iucA;iucB;iucC;iucD;iutA;lpfA-O113;senB;sigA | NA | N | NA | IS1(1);IS30(1);IS600(1) |
| RM8376 | lineage2.1 | lineage2 | lineage2.1 | 2/2 | 152 | ST152 Cplx | acrF;blaEC;emrD;emrE;espX1;ipaH3;ipaHa;ipaHb;ipaHd;ipaHe;iucA;iucB;iucC;iucD;iutA;lpfA-O113;senB;sigA | NA | N | NA | IS1(1);IS30(1);IS600(1) |
| UKMCC_1015 | lineage2.1 | lineage2 | lineage2.1 | 2/2 | 152 | ST152 Cplx | acrF;blaEC;emrD;emrE;espX1;ipaH3;ipaHa;ipaHb;ipaHd;ipaHe;iucA;iucB;iucC;iucD;iutA;lpfA-O113;senB;sigA | NA | N | NA | IS1(1);IS30(1);IS600(1) |

### Notes on example output

**Mykrobe genotyping** — all five samples belong to lineage 2, the globally dominant lineage of *S. sonnei*. Four samples are lineage 2.1 (the most widely circulating clade); ATCC_29930 is lineage 2.6, an older divergent clade. Mykrobe confidence is 2/2 (all good nodes called at the correct tree depth) for every sample. No subclade or genotype name is assigned where the panel does not resolve below clade level.

**MLST** — two sequence types are represented: ST5479 (AR_0030, AR_0426) and ST152 (ATCC_29930, RM8376, UKMCC_1015). ST152 belongs to the ST152 complex, a well-characterised *S. sonnei* lineage 2 clonal complex. ST5479 is not currently assigned to a complex in `assets/sonnei_st_complexes.tsv`.

**AMR genes** — all samples carry the core *S. sonnei* chromosomal complement (`acrF`, `blaEC`, `emrD`, `emrE`) plus a range of virulence-associated genes routinely detected by AMRFinder in this species (e.g. `ipaH` paralogues, `iuc` iron-uptake locus, `sigA`, `senB`). AR_0030 additionally carries `blaTEM-1`, indicating a β-lactam resistance determinant.

**pINV and PlasmidFinder** — `pinv_present = N` and `plasmidfinder_replicons = NA` for all samples. This is expected: these are chromosome-only RefSeq assemblies that do not include the pINV virulence plasmid sequence. In real clinical draft assemblies, contigs from pINV will be present and these columns will be populated.

**IS elements** — IS1, IS30, and IS600 are each detected as single copies in all five assemblies. These IS elements are characteristic of *S. sonnei* and their consistent presence across all samples is a useful quality indicator that the IS screen is functioning correctly.

---

## Citation

If you use this pipeline, please cite the underlying tools:

- **Mykrobe / sonnei typing**: Hawkey *et al.* (2021) *Nat Commun* 12:2684
- **mlst**: Seemann T. mlst. https://github.com/tseemann/mlst
- **AMRFinder Plus**: Feldgarden *et al.* (2021) *Sci Rep* 11:12728
- **PlasmidFinder**: Carattoli *et al.* (2014) *Antimicrob Agents Chemother* 58:3895–3903
- **Mash**: Ondov *et al.* (2016) *Genome Biol* 17:132
