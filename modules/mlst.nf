// ── MLST: 7-locus Achtman MLST ──────────────────────────────────────────────

process MLST {
    tag "${sample_id}"
    label 'low'

    conda     "${projectDir}/envs/mlst.yml"
    container 'staphb/mlst:2.23.0'

    input:
    tuple val(sample_id), path(fasta)

    output:
    tuple val(sample_id), path("${sample_id}_mlst.tsv")

    script:
    """
    mlst \\
        --scheme ecoli_achtman_4 \\
        --threads ${task.cpus} \\
        --label ${sample_id} \\
        ${fasta} > ${sample_id}_mlst.tsv \\
    || printf '%s\t%s\t%s\n' ${sample_id} ecoli_achtman_4 NA > ${sample_id}_mlst.tsv
    """
}
