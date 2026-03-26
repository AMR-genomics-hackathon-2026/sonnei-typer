// ── MICROREACT_UPLOAD: post results table to Microreact ─────────────────────

process MICROREACT_UPLOAD {
    label 'low'

    conda     "${projectDir}/envs/utils.yml"
    container 'python:3.11-slim'

    // Token read from Nextflow secret (set with: nextflow secrets set MICROREACT_TOKEN <value>)
    // Falls back to MICROREACT_TOKEN environment variable if secret is not set
    secret 'MICROREACT_TOKEN'

    publishDir "${params.outdir}", mode: 'copy', overwrite: true

    input:
    path(results_tsv)
    val(project_name)

    output:
    path "microreact_url.txt"

    script:
    """
    upload_microreact.py \\
        --input    ${results_tsv} \\
        --project  "${project_name}" \\
        --token    "\${MICROREACT_TOKEN}" \\
        --output   microreact_url.txt
    """
}
