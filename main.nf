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

    // Collect per-sample results; join on sample_id with remainder=true so
    // a tool failure for one sample does not drop that sample from the table
    ch_aggregate = PARSE_MYKROBE.out
        .join(MLST.out,       remainder: true)
        .join(AMRFINDER.out,  remainder: true)
        .join(SHIGATYPER.out, remainder: true)
        .map { id, mykrobe, mlst, amrfinder, shigatyper ->
            tuple(id,
                  mykrobe    ?: file("NO_FILE_mykrobe"),
                  mlst       ?: file("NO_FILE_mlst"),
                  amrfinder  ?: file("NO_FILE_amrfinder"),
                  shigatyper ?: file("NO_FILE_shigatyper"))
        }
        .collect { it }

    AGGREGATE(
        ch_aggregate,
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
