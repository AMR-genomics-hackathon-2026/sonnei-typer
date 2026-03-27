#!/usr/bin/env python3
"""Upload confirmed S. sonnei assemblies to Pathogenwatch and return batch results.

Current outputs focus on:
- genome processing status and species assignment
- collection metadata
- cgMLST assignment where available
- labels of genomes in the threshold=10 cluster search

Forward-looking checks are included for:
- collection tree availability
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import json
import mimetypes
import os
import sys
import time
from pathlib import Path

import requests


DEFAULT_BASE_URL = "https://next.pathogen.watch"
FASTA_SUFFIXES = {".fa", ".fasta", ".fna", ".fas"}
TERMINAL_STATUSES = {"COMPLETE", "FAILEDQC", "FAILED", "ERROR"}


class PathogenwatchError(RuntimeError):
    pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Pathogenwatch upload and cluster search for S. sonnei")
    parser.add_argument("--samplesheet", required=True, help="CSV with id,fasta columns")
    parser.add_argument("--sample-output", required=True, help="Per-sample TSV output path")
    parser.add_argument("--collection-output", required=True, help="Collection JSON output path")
    parser.add_argument("--summary-output", required=True, help="Summary JSON output path")
    parser.add_argument("--collection-name", required=True, help="Collection/folder name prefix")
    parser.add_argument("--threshold", type=int, default=10, help="Cluster threshold to request")
    parser.add_argument("--poll-seconds", type=int, default=60, help="Seconds between Pathogenwatch polls")
    parser.add_argument("--max-wait-seconds", type=int, default=1800, help="Maximum total poll time")
    parser.add_argument("--base-url", default=os.environ.get("PW_API_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--api-key", default=os.environ.get("PW_API_KEY"))
    return parser.parse_args()


def require_api_key(api_key: str | None) -> str:
    if not api_key:
        raise PathogenwatchError("Missing PW_API_KEY / --api-key")
    return api_key


def session_for(api_key: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({"X-API-Key": api_key})
    return session


def request_json(
    session: requests.Session,
    method: str,
    url: str,
    *,
    params: dict[str, object] | None = None,
    json_body: object | None = None,
    timeout: int = 120,
) -> object:
    response = session.request(method, url, params=params, json=json_body, timeout=timeout)
    response.raise_for_status()
    if not response.text:
        return None
    return response.json()


def sha1_file(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_samplesheet(path: Path) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    with path.open() as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            sample_id = (row.get("id") or "").strip()
            fasta = Path((row.get("fasta") or "").strip())
            if not sample_id or not fasta.exists() or fasta.suffix.lower() not in FASTA_SUFFIXES:
                raise PathogenwatchError(f"Invalid samplesheet row: {row}")
            rows.append({"id": sample_id, "fasta": str(fasta)})
    if not rows:
        raise PathogenwatchError("No rows found in samplesheet")
    return rows


def create_folder(session: requests.Session, base_url: str, name: str) -> dict[str, object]:
    payload = request_json(session, "POST", f"{base_url}/api/folders/create", json_body={"name": name})
    if not isinstance(payload, dict):
        raise PathogenwatchError("Unexpected folder response shape")
    return payload


def upload_to_signed_url(upload_url: str, fasta_path: Path) -> None:
    content_type = mimetypes.guess_type(str(fasta_path))[0] or "application/octet-stream"
    payload = gzip.compress(fasta_path.read_bytes())
    response = requests.put(
        upload_url,
        data=payload,
        headers={
            "Content-Type": content_type,
            "Content-Length": str(len(payload)),
            "Content-Encoding": "gzip",
        },
        timeout=300,
    )
    response.raise_for_status()


def upload_genome(
    session: requests.Session,
    base_url: str,
    folder_id: int,
    sample_id: str,
    fasta_path: Path,
) -> dict[str, object]:
    checksum = sha1_file(fasta_path)
    store = request_json(
        session,
        "POST",
        f"{base_url}/api/genomes/store",
        params={"checksum": checksum, "type": "assembly"},
    )
    if not isinstance(store, dict):
        raise PathogenwatchError("Unexpected genomes/store response shape")
    if store.get("upload"):
        upload_to_signed_url(str(store["uploadUrl"]), fasta_path)
    genome = request_json(
        session,
        "POST",
        f"{base_url}/api/genomes/create",
        json_body={"folderId": int(folder_id), "checksum": checksum, "name": sample_id},
    )
    if not isinstance(genome, dict):
        raise PathogenwatchError("Unexpected genomes/create response shape")
    return {
        "sample": sample_id,
        "fasta": str(fasta_path),
        "checksum": checksum,
        "id": genome["id"],
        "uuid": genome["uuid"],
    }


def genome_details(session: requests.Session, base_url: str, genome_uuid: str) -> dict[str, object]:
    payload = request_json(session, "GET", f"{base_url}/api/genomes/details", params={"id": genome_uuid})
    if not isinstance(payload, dict):
        raise PathogenwatchError("Unexpected genomes/details response shape")
    return payload


def group_genomes(session: requests.Session, base_url: str, genome_ids: list[int]) -> list[dict[str, object]]:
    payload = request_json(
        session,
        "POST",
        f"{base_url}/api/genomes/group",
        json_body={"ids": genome_ids},
    )
    if not isinstance(payload, list):
        raise PathogenwatchError("Unexpected genomes/group response shape")
    return payload


def wait_for_processing(
    session: requests.Session,
    base_url: str,
    uploaded: list[dict[str, object]],
    poll_seconds: int,
    max_wait_seconds: int,
) -> tuple[dict[str, dict[str, object]], list[dict[str, object]]]:
    deadline = time.monotonic() + max_wait_seconds
    genome_ids = [int(item["id"]) for item in uploaded]
    latest_details: dict[str, dict[str, object]] = {}
    latest_groups: list[dict[str, object]] = []
    while time.monotonic() < deadline:
        latest_details = {
            str(item["uuid"]): genome_details(session, base_url, str(item["uuid"]))
            for item in uploaded
        }
        latest_groups = group_genomes(session, base_url, genome_ids)
        if latest_groups and all(str(d.get("status")) in TERMINAL_STATUSES for d in latest_details.values()):
            break
        time.sleep(poll_seconds)
    return latest_details, latest_groups


def create_collection(
    session: requests.Session,
    base_url: str,
    organism_id: str,
    genome_ids: list[int],
    name: str,
) -> dict[str, object]:
    payload = request_json(
        session,
        "POST",
        f"{base_url}/api/collections/create",
        json_body={"organismId": organism_id, "genomeIds": genome_ids, "name": name},
    )
    if not isinstance(payload, dict):
        raise PathogenwatchError("Unexpected collections/create response shape")
    return payload


def collection_details(session: requests.Session, base_url: str, collection_uuid: str) -> dict[str, object]:
    payload = request_json(
        session,
        "GET",
        f"{base_url}/api/collections/details",
        params={"uuid": collection_uuid},
    )
    if not isinstance(payload, dict):
        raise PathogenwatchError("Unexpected collections/details response shape")
    return payload


def collection_genomes(session: requests.Session, base_url: str, collection_id: int) -> dict[str, object]:
    payload = request_json(
        session,
        "GET",
        f"{base_url}/api/collections/genomes",
        params={"collectionId": collection_id},
    )
    if not isinstance(payload, dict):
        raise PathogenwatchError("Unexpected collections/genomes response shape")
    return payload


def trigger_recluster(session: requests.Session, base_url: str, genome_uuid: str) -> dict[str, object]:
    payload = request_json(
        session,
        "POST",
        f"{base_url}/api/genomes/cluster/recluster",
        json_body={"id": genome_uuid},
    )
    if not isinstance(payload, dict):
        raise PathogenwatchError("Unexpected genomes/cluster/recluster response shape")
    return payload


def cluster_details_threshold(
    session: requests.Session,
    base_url: str,
    genome_uuid: str,
    threshold: int,
) -> dict[str, object]:
    payload = request_json(
        session,
        "GET",
        f"{base_url}/api/genomes/cluster/details",
        params={"id": genome_uuid, "threshold": threshold},
    )
    if not isinstance(payload, dict):
        raise PathogenwatchError("Unexpected genomes/cluster/details response shape")
    return payload


def cluster_labels(cluster_payload: dict[str, object], focal_name: str) -> list[str]:
    nodes = cluster_payload.get("nodes") or {}
    if not isinstance(nodes, dict):
        return []
    labels = sorted(
        {
            str(node.get("label"))
            for node in nodes.values()
            if isinstance(node, dict) and node.get("label") and str(node.get("label")) != focal_name
        }
    )
    return labels


def write_sample_tsv(path: Path, rows: list[dict[str, object]]) -> None:
    columns = [
        "sample",
        "fasta",
        "pw_status",
        "pw_species",
        "pw_species_confirmed",
        "pw_organism_id",
        "pw_genome_id",
        "pw_genome_uuid",
        "pw_checksum",
        "pw_collection_id",
        "pw_collection_uuid",
        "pw_collection_url",
        "pw_cgmlst_st",
        "pw_cluster10_status",
        "pw_cluster10_count",
        "pw_cluster10_labels",
        "pw_tree_available",
        "pw_amrfinder_available",
    ]
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def main() -> int:
    args = parse_args()
    api_key = require_api_key(args.api_key)
    base_url = args.base_url.rstrip("/")
    samples = read_samplesheet(Path(args.samplesheet))
    session = session_for(api_key)

    folder = create_folder(session, base_url, args.collection_name)
    uploaded = [
        upload_genome(session, base_url, int(folder["id"]), row["id"], Path(row["fasta"]))
        for row in samples
    ]
    details_by_uuid, groups = wait_for_processing(
        session,
        base_url,
        uploaded,
        poll_seconds=args.poll_seconds,
        max_wait_seconds=args.max_wait_seconds,
    )

    sonnei_group = next((g for g in groups if str(g.get("organismId")) == "624" and g.get("supported")), None)
    collection = None
    collection_meta: dict[str, object] = {}
    if sonnei_group and len(uploaded) > 1:
        collection = create_collection(
            session,
            base_url,
            organism_id=str(sonnei_group["organismId"]),
            genome_ids=[int(x) for x in sonnei_group["ids"]],
            name=args.collection_name,
        )
        collection_meta = collection_details(session, base_url, str(collection["uuid"]))
        collection_genomes(session, base_url, int(collection["id"]))

    uploaded_by_uuid = {str(item["uuid"]): item for item in uploaded}
    rows: list[dict[str, object]] = []
    for row in samples:
        uploaded_genome = next(item for item in uploaded if item["sample"] == row["id"])
        genome_uuid = str(uploaded_genome["uuid"])
        details = details_by_uuid.get(genome_uuid, {})
        cluster_payload: dict[str, object] = {"status": "NOT_REQUESTED", "threshold": args.threshold, "nodes": {}}
        if str(details.get("status")) in {"COMPLETE", "FAILEDQC"}:
            cluster_payload = cluster_details_threshold(session, base_url, genome_uuid, args.threshold)
            if str(cluster_payload.get("status")) != "READY":
                trigger_recluster(session, base_url, genome_uuid)
                time.sleep(args.poll_seconds)
                cluster_payload = cluster_details_threshold(session, base_url, genome_uuid, args.threshold)
        labels = cluster_labels(cluster_payload, str(details.get("name") or row["id"]))
        rows.append(
            {
                "sample": row["id"],
                "fasta": row["fasta"],
                "pw_status": details.get("status", "UNKNOWN"),
                "pw_species": details.get("species", "NA"),
                "pw_species_confirmed": str(details.get("species") == "Shigella sonnei"),
                "pw_organism_id": details.get("organismId", "NA"),
                "pw_genome_id": uploaded_genome["id"],
                "pw_genome_uuid": genome_uuid,
                "pw_checksum": uploaded_genome["checksum"],
                "pw_collection_id": collection.get("id") if collection else "NA",
                "pw_collection_uuid": collection.get("uuid") if collection else "NA",
                "pw_collection_url": collection.get("url") if collection else "NA",
                "pw_cgmlst_st": details.get("cgmlstSt", "NA"),
                "pw_cluster10_status": cluster_payload.get("status", "UNKNOWN"),
                "pw_cluster10_count": len(labels),
                "pw_cluster10_labels": ";".join(labels) if labels else "NA",
                "pw_tree_available": str(bool(collection_meta.get("hasTreeMethods"))) if collection_meta else "False",
            }
        )

    sample_output = Path(args.sample_output)
    collection_output = Path(args.collection_output)
    summary_output = Path(args.summary_output)
    write_sample_tsv(sample_output, rows)
    collection_output.write_text(json.dumps({"folder": folder, "groups": groups, "collection": collection, "collectionMeta": collection_meta}, indent=2) + "\n")
    summary_output.write_text(json.dumps({"samples": rows}, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except requests.HTTPError as exc:
        print(f"HTTP error: {exc}", file=sys.stderr)
        raise
    except PathogenwatchError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
