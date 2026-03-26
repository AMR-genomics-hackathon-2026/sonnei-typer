// ── AMRFINDER PLUS: AMR and virulence gene detection ────────────────────────

process AMRFINDER {
    tag "${sample_id}"
    label 'medium'

    conda     "${projectDir}/envs/amrfinder.yml"
    container 'staphb/ncbi-amrfinderplus:3.12.8'

    input:
    tuple val(sample_id), path(fasta)

    output:
    tuple val(sample_id), path("${sample_id}_amrfinder.tsv")

    script:
    """
    amrfinder \\
        --nucleotide ${fasta} \\
        --organism Escherichia \\
        --plus \\
        --threads ${task.cpus} \\
        --name ${sample_id} \\
        --output ${sample_id}_amrfinder.tsv \\
    || printf 'Name\tProtein identifier\tContig id\tStart\tStop\tStrand\tGene symbol\tSequence name\tScope\tElement type\tElement subtype\tClass\tSubclass\tMethod\tTarget length\tReference sequence length\t% Coverage of reference sequence\t% Identity to reference sequence\tAlignment length\tAccession of closest sequence\tName of closest sequence\tHMM id\tHMM description\n' > ${sample_id}_amrfinder.tsv
    """
}
