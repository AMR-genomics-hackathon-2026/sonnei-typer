// ── AMRFINDER PLUS: AMR and virulence gene detection ────────────────────────

process AMRFINDER {
    tag "${sample_id}"
    label 'medium'

    conda     "${projectDir}/envs/amrfinder.yml"
    container 'quay.io/biocontainers/ncbi-amrfinderplus:4.2.7--hf69ffd2_0'

    input:
    tuple val(sample_id), path(fasta)

    output:
    tuple val(sample_id), path("${sample_id}_amrfinder.tsv")

    script:
    """
    # Download database if not already present
    amrfinder -u 2>/dev/null || true

    amrfinder \\
        --nucleotide ${fasta} \\
        --organism Escherichia \\
        --plus \\
        --threads ${task.cpus} \\
        --name ${sample_id} \\
        --output ${sample_id}_amrfinder.tsv \\
    || echo -e 'Name\tGene symbol\tElement type\tClass\tSubclass' > ${sample_id}_amrfinder.tsv
    """
}
