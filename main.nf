#!/usr/bin/env nextflow
nextflow.enable.dsl = 2

include { MYKROBE        } from './modules/mykrobe'
include { PARSE_MYKROBE  } from './modules/mykrobe'
include { MLST           } from './modules/mlst'
include { AMRFINDER      } from './modules/amrfinder'
include { SHIGATYPER     } from './modules/shigatyper'
include { AGGREGATE      } from './modules/aggregate'
include { MICROREACT_UPLOAD } from './modules/microreact_upload'

// ── Parameter validation ────────────────────────────────────────────────────
if (!params.samplesheet) {
    error "ERROR: --samplesheet is required. See README.md for samplesheet format."
}

// ── Workflow ────────────────────────────────────────────────────────────────
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

    // Run all tools in parallel per sample
    MYKROBE(ch_samples)
    MLST(ch_samples)
    AMRFINDER(ch_samples)
    SHIGATYPER(ch_samples)

    // Parse Mykrobe JSON → TSV
    PARSE_MYKROBE(MYKROBE.out)

    // Collect per-tool outputs as separate file lists for aggregation
    ch_mykrobe_files   = PARSE_MYKROBE.out.map { id, f -> f }.collect()
    ch_mlst_files      = MLST.out.map       { id, f -> f }.collect()
    ch_amrfinder_files = AMRFINDER.out.map  { id, f -> f }.collect()
    ch_shigatyper_files = SHIGATYPER.out.map { id, f -> f }.collect()

    AGGREGATE(
        ch_mykrobe_files,
        ch_mlst_files,
        ch_amrfinder_files,
        ch_shigatyper_files,
        file("${projectDir}/assets/sonnei_st_complexes.tsv")
    )

    // Optional Microreact upload
    if (params.upload_microreact) {
        MICROREACT_UPLOAD(
            AGGREGATE.out.results,
            params.microreact_project
        )
    }
}

// ── Workflow completion summary ─────────────────────────────────────────────
workflow.onComplete {
    log.info """
    ====================================================
    sonnei-typer completed ${workflow.success ? 'successfully' : 'with errors'}
    Results : ${params.outdir}
    Duration: ${workflow.duration}
    ====================================================
    """.stripIndent()
}
