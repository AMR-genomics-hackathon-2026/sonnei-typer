// ── PINV_SCREEN: pINV virulence plasmid detection via BLAST ──────────────────
// Screens for pINV-specific marker genes (icsA/virG, virF, virB, ipaB/C/D).
// Uses blastn against a curated pINV gene FASTA in assets/.
// pINV is the ~214 kb invasion plasmid essential for S. sonnei pathogenicity.

process ABRICATE_VFDB {
    tag "${sample_id}"
    label 'low'

    conda     "${projectDir}/envs/mlst.yml"
    container 'staphb/mlst:2.23.0'

    input:
    tuple val(sample_id), path(fasta)
    path(pinv_db)

    output:
    tuple val(sample_id), path("${sample_id}_vfdb.tsv")

    script:
    """
    makeblastdb -in ${pinv_db} -dbtype nucl -out pinv_db 2>/dev/null || \
    makeblastdb -in ${pinv_db} -dbtype nucl -out pinv_db -logfile /dev/null 2>/dev/null

    blastn \\
        -query ${fasta} \\
        -db pinv_db \\
        -out blast_pinv.tsv \\
        -outfmt "6 qseqid sseqid pident length qstart qend slen" \\
        -perc_identity 80 \\
        -num_threads ${task.cpus} \\
        -max_hsps 1 \\
        -dust no 2>/dev/null || true

    # Report: gene, identity, coverage
    echo -e "sample\\tgene\\t%identity\\t%coverage" > ${sample_id}_vfdb.tsv
    if [ -s blast_pinv.tsv ]; then
        awk -v s="${sample_id}" '{
            cov = (\$4 / \$7) * 100
            if (cov >= 80) print s, \$2, \$3, cov
        }' OFS="\\t" blast_pinv.tsv \\
        | sort -k2,2 -k4,4rn \\
        | awk '!seen[\$2]++' >> ${sample_id}_vfdb.tsv
    fi
    """
}
