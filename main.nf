#!/usr/bin/env nextflow
nextflow.enable.dsl = 2

include { SPECIES_CHECK      } from './modules/species_check'
include { MYKROBE            } from './modules/mykrobe'
include { PARSE_MYKROBE      } from './modules/mykrobe'
include { MLST               } from './modules/mlst'
include { AMRFINDER          } from './modules/amrfinder'
include { PLASMIDFINDER      } from './modules/plasmidfinder'
include { ABRICATE_VFDB      } from './modules/abricate'
include { IS_SCREEN          } from './modules/is_screen'
include { AGGREGATE          } from './modules/aggregate'
include { MICROREACT_UPLOAD  } from './modules/microreact_upload'

// ── Parameter validation ─────────────────────────────────────────────────────
if (!params.samplesheet) {
    error "ERROR: --samplesheet is required. See README.md for samplesheet format."
}

// ── Workflow ─────────────────────────────────────────────────────────────────
workflow {

    // Read samplesheet: id,fasta
    ch_samples = Channel
        .fromPath(params.samplesheet)
        .splitCsv(header: true)
        .map { row ->
            def fasta = file(row.fasta)
            if (!fasta.exists()) error "FASTA file not found for sample '${row.id}': ${row.fasta}"
            tuple(row.id, fasta)
        }

    // ── Step 1: Species check (Mash) ─────────────────────────────────────────
    ch_ref_sketch = file("${projectDir}/assets/sonnei_species_refs.msh")
    SPECIES_CHECK(ch_samples, ch_ref_sketch)

    // Join species result back with original fasta channel, then branch
    ch_branched = ch_samples
        .join(SPECIES_CHECK.out)
        .map { id, fasta, result_file ->
            def tokens = result_file.text.trim().tokenize()
            def species = tokens[0] ?: "Unknown"
            def dist    = tokens[1] ? tokens[1].toFloat() : 1.0
            def confirmed = (species == "Shigella_sonnei" && dist < 0.05)
            tuple(id, fasta, species, dist, confirmed)
        }
        .branch {
            confirmed: it[4] == true
            rejected:  true
        }

    // Log rejected samples
    ch_branched.rejected
        .map { id, fasta, species, dist, ok ->
            log.warn "Sample '${id}' rejected: closest species = ${species} (Mash dist = ${dist}). Skipping all typing modules."
        }

    // Confirmed samples (strip species/dist columns for downstream)
    ch_confirmed = ch_branched.confirmed.map { id, fasta, sp, d, ok -> tuple(id, fasta) }

    // ── Step 2: Run all typing tools on confirmed S. sonnei samples ───────────
    MYKROBE(ch_confirmed)
    MLST(ch_confirmed)
    AMRFINDER(ch_confirmed)
    PLASMIDFINDER(ch_confirmed)
    ch_pinv_db = file("${projectDir}/assets/pinv_markers.fasta")
    ABRICATE_VFDB(ch_confirmed, ch_pinv_db)

    ch_is_db = file("${projectDir}/assets/shigella_is_elements.fasta")
    IS_SCREEN(ch_confirmed, ch_is_db)

    // Parse Mykrobe JSON → TSV
    PARSE_MYKROBE(MYKROBE.out)

    // ── Step 3: Collect and aggregate ────────────────────────────────────────
    ch_mykrobe_files      = PARSE_MYKROBE.out.map  { id, f -> f }.collect()
    ch_mlst_files         = MLST.out.map            { id, f -> f }.collect()
    ch_amrfinder_files    = AMRFINDER.out.map       { id, f -> f }.collect()
    ch_plasmidfinder_files= PLASMIDFINDER.out.map   { id, f -> f }.collect()
    ch_abricate_files     = ABRICATE_VFDB.out.map   { id, f -> f }.collect()
    ch_is_screen_files    = IS_SCREEN.out.map        { id, f -> f }.collect()

    AGGREGATE(
        ch_mykrobe_files,
        ch_mlst_files,
        ch_amrfinder_files,
        ch_plasmidfinder_files,
        ch_abricate_files,
        ch_is_screen_files,
        file("${projectDir}/assets/sonnei_st_complexes.tsv")
    )

    // ── Step 4: Optional Microreact upload ───────────────────────────────────
    if (params.upload_microreact) {
        MICROREACT_UPLOAD(
            AGGREGATE.out.results,
            params.microreact_project
        )
    }
}

// ── Workflow completion summary ───────────────────────────────────────────────
workflow.onComplete {
    log.info """
    ====================================================
    sonnei-typer completed ${workflow.success ? 'successfully' : 'with errors'}
    Results : ${params.outdir}
    Duration: ${workflow.duration}
    ====================================================
    """.stripIndent()
}
