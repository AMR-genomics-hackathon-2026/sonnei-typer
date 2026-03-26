// ── AGGREGATE: merge all per-sample results into one table ──────────────────

process AGGREGATE {
    label 'low'

    conda     "${projectDir}/envs/utils.yml"
    container 'python:3.11-slim'

    publishDir "${params.outdir}", mode: 'copy', overwrite: true

    input:
    path(mykrobe_files)
    path(mlst_files)
    path(amrfinder_files)
    path(plasmidfinder_files)
    path(abricate_files)
    path(is_screen_files)
    path(st_complexes)

    output:
    path "sonnei_typer_results.tsv", emit: results

    script:
    """
    aggregate_results.py \\
        --mykrobe       ${mykrobe_files} \\
        --mlst          ${mlst_files} \\
        --amrfinder     ${amrfinder_files} \\
        --plasmidfinder ${plasmidfinder_files} \\
        --abricate      ${abricate_files} \\
        --is-screen     ${is_screen_files} \\
        --st-complexes  ${st_complexes} \\
        --output sonnei_typer_results.tsv
    """
}
