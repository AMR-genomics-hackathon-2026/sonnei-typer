// ── IS_SCREEN: IS element detection via BLAST ────────────────────────────────
// Screens for key IS elements relevant to S. sonnei using a curated reference FASTA.
// Uses blastn (already present as mlst/plasmidfinder dependency).

process IS_SCREEN {
    tag "${sample_id}"
    label 'low'

    conda     "${projectDir}/envs/mlst.yml"
    container 'staphb/mlst:2.23.0'

    input:
    tuple val(sample_id), path(fasta)
    path(is_db)

    output:
    tuple val(sample_id), path("${sample_id}_is_screen.tsv")

    script:
    """
    # Make BLAST database from IS reference sequences
    makeblastdb -in ${is_db} -dbtype nucl -out is_db -logfile /dev/null 2>/dev/null || \
    makeblastdb -in ${is_db} -dbtype nucl -out is_db 2>/dev/null

    # BLAST assembly against IS elements
    blastn \\
        -query ${fasta} \\
        -db is_db \\
        -out blast_raw.tsv \\
        -outfmt "6 qseqid sseqid pident length qstart qend slen" \\
        -perc_identity 85 \\
        -num_threads ${task.cpus} \\
        -dust no 2>/dev/null || true

    # Summarise: IS element, number of insertions, contig locations
    echo -e "sample\\tIS_element\\tcopies\\tlocations" > ${sample_id}_is_screen.tsv
    if [ -s blast_raw.tsv ]; then
        awk -v s="${sample_id}" '
        {
            is[\$2]++
            loc[\$2] = loc[\$2] (loc[\$2]=="" ? "" : ";") \$1 ":" \$5 "-" \$6
        }
        END {
            for (e in is) print s, e, is[e], loc[e]
        }
        ' OFS="\\t" blast_raw.tsv >> ${sample_id}_is_screen.tsv
    fi
    """
}
