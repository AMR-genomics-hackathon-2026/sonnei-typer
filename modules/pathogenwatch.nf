// ── PATHOGENWATCH: upload confirmed S. sonnei assemblies and fetch cgMLST + cluster labels ──

process PATHOGENWATCH {
    label 'low'

    conda     "${projectDir}/envs/utils.yml"
    container 'python:3.11-slim'

    secret 'PW_API_KEY'

    input:
    val(samples)

    output:
    path "pathogenwatch_samples.tsv", emit: results
    path "pathogenwatch_collection.json", emit: collection
    path "pathogenwatch_summary.json", emit: summary

    script:
    def rows = samples.collect { sid, fasta -> "${sid},${fasta}" }.join('\n')
    def collectionName = params.pathogenwatch_collection_name ?: "sonnei-typer-${workflow.runName}"
    """
    cat > pathogenwatch_samplesheet.csv <<'CSV'
    id,fasta
    ${rows}
    CSV

    pathogenwatch_cluster_search.py \\
        --samplesheet      pathogenwatch_samplesheet.csv \\
        --collection-name  "${collectionName}" \\
        --threshold        ${params.pathogenwatch_cluster_threshold} \\
        --poll-seconds     ${params.pathogenwatch_poll_seconds} \\
        --max-wait-seconds ${params.pathogenwatch_max_wait_seconds} \\
        --sample-output    pathogenwatch_samples.tsv \\
        --collection-output pathogenwatch_collection.json \\
        --summary-output   pathogenwatch_summary.json
    """
}
