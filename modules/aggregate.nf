// ── AGGREGATE: merge all per-sample results into one table ──────────────────

process AGGREGATE {
    label 'low'

    conda     "${projectDir}/envs/utils.yml"
    container 'python:3.11-slim'

    publishDir "${params.outdir}", mode: 'copy', overwrite: true

    input:
    val(sample_results)        // collected list of [id, mykrobe, mlst, amrfinder, shigatyper]
    path(st_complexes)         // assets/sonnei_st_complexes.tsv

    output:
    path "sonnei_typer_results.tsv", emit: results

    script:
    // Build space-separated file lists for each tool
    def mykrobe_files   = sample_results.collect { it[1] }.join(' ')
    def mlst_files      = sample_results.collect { it[2] }.join(' ')
    def amrfinder_files = sample_results.collect { it[3] }.join(' ')
    def shigatyper_files = sample_results.collect { it[4] }.join(' ')

    """
    aggregate_results.py \\
        --mykrobe   ${mykrobe_files} \\
        --mlst      ${mlst_files} \\
        --amrfinder ${amrfinder_files} \\
        --shigatyper ${shigatyper_files} \\
        --st-complexes ${st_complexes} \\
        --output sonnei_typer_results.tsv
    """
}
