// ── SPECIES_CHECK: Mash distance to confirm Shigella sonnei ─────────────────

process SPECIES_CHECK {
    tag "${sample_id}"
    label 'low'

    conda     "${projectDir}/envs/mash.yml"
    container 'quay.io/biocontainers/mash:2.3--hd3113eb_5'

    input:
    tuple val(sample_id), path(fasta)
    path(reference_sketch)

    output:
    tuple val(sample_id), path(fasta), path("${sample_id}_species.txt")

    script:
    """
    mash dist ${reference_sketch} ${fasta} \\
        2>/dev/null \\
        | sort -k3,3n \\
        | awk 'NR==1 {
            split(\$1, a, "/")
            ref = a[length(a)]
            gsub(/\\.fasta/, "", ref)
            print ref, \$3
        }' > ${sample_id}_species.txt

    # If mash produced no output, write unknown
    [ -s ${sample_id}_species.txt ] || echo "Unknown 1.0" > ${sample_id}_species.txt
    """
}
