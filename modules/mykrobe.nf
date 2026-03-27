// ── MYKROBE: Hawkey 2021 S. sonnei genotyping ───────────────────────────────

process MYKROBE {
    tag "${sample_id}"
    label 'medium'

    conda     "${projectDir}/envs/mykrobe.yml"
    container 'staphb/mykrobe:0.13.0'

    input:
    tuple val(sample_id), path(fasta)

    output:
    tuple val(sample_id), path("${sample_id}_mykrobe.json")

    script:
    """
    mykrobe predict \\
        --sample ${sample_id} \\
        --species sonnei \\
        --format json \\
        --seq ${fasta} \\
        --panel 20210201 \\
        --output ${sample_id}_mykrobe.json \\
        --threads ${task.cpus} \\
        2>${sample_id}_mykrobe.log \\
    || echo '{"error":"mykrobe_failed","sample":"${sample_id}"}' > ${sample_id}_mykrobe.json
    """
}

// ── PARSE_MYKROBE: JSON → single-row TSV ────────────────────────────────────

process PARSE_MYKROBE {
    tag "${sample_id}"
    label 'low'

    conda     "${projectDir}/envs/utils.yml"
    container 'python:3.11'

    input:
    tuple val(sample_id), path(json)
    path(parse_script)

    output:
    tuple val(sample_id), path("${sample_id}_mykrobe_parsed.tsv")

    script:
    """
    python3 ${parse_script} ${json} ${sample_id} > ${sample_id}_mykrobe_parsed.tsv
    """
}
