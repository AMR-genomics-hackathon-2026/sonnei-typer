// ── SHIGATYPER: serotype confirmation ───────────────────────────────────────

process SHIGATYPER {
    tag "${sample_id}"
    label 'low'

    conda     "${projectDir}/envs/shigatyper.yml"
    container 'staphb/shigatyper:2.0.5'

    input:
    tuple val(sample_id), path(fasta)

    output:
    tuple val(sample_id), path("${sample_id}_shigatyper.tsv")

    script:
    """
    shigatyper \\
        --SE ${fasta} \\
        --name ${sample_id} \\
        --outdir ./ \\
    2>${sample_id}_shigatyper.log \\
    || printf 'sample\tHit\tNumber of reads\t%% reads\tLength\t%% covered\t%% identity\tNotes\n${sample_id}\tNA\tNA\tNA\tNA\tNA\tNA\ttool_failed\n' > ${sample_id}_shigatyper.tsv

    # ShigaTyper writes to <name>.tsv; rename to our convention if needed
    [ -f "${sample_id}.tsv" ] && mv ${sample_id}.tsv ${sample_id}_shigatyper.tsv || true
    """
}
