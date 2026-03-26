// ── PLASMIDFINDER: plasmid replicon typing ───────────────────────────────────

process PLASMIDFINDER {
    tag "${sample_id}"
    label 'low'

    conda     "${projectDir}/envs/plasmidfinder.yml"
    container 'staphb/plasmidfinder:2.1.6'

    input:
    tuple val(sample_id), path(fasta)

    output:
    tuple val(sample_id), path("${sample_id}_plasmidfinder.tsv")

    script:
    """
    # Locate database bundled with the conda package
    BLASTN_PATH=\$(which blastn)
    ENV_PREFIX=\$(dirname \$(dirname "\$BLASTN_PATH"))
    DB_PATH=\$(find "\$ENV_PREFIX/share" -name "database" -type d 2>/dev/null | head -1)
    [ -z "\$DB_PATH" ] && DB_PATH="/database"
    BLASTN_DIR=\$(dirname "\$BLASTN_PATH")

    plasmidfinder.py \\
        -i ${fasta} \\
        -o ./ \\
        -mp "\$BLASTN_DIR" \\
        -p "\$DB_PATH" \\
        -l 0.60 \\
        -t 0.90 \\
        -q \\
        2>${sample_id}_plasmidfinder.log \\
    || true

    # Parse results_tab.tsv → our naming convention
    if [ -f results_tab.tsv ] && [ \$(wc -l < results_tab.tsv) -gt 1 ]; then
        cp results_tab.tsv ${sample_id}_plasmidfinder.tsv
    else
        printf 'Plasmid\\tIdentity\\tQuery / Template length\\tContig\\tPosition in contig\\tNote\\tAccession number\\n' \
            > ${sample_id}_plasmidfinder.tsv
        printf 'No replicons found\\tNA\\tNA\\tNA\\tNA\\tNA\\tNA\\n' \
            >> ${sample_id}_plasmidfinder.tsv
    fi
    """
}
