#!/usr/bin/env python3
"""Audit an INFOCOM 2027 review PDF and optional anonymous artifact ZIP."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import stat
import sys
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

try:
    from pypdf import PdfReader
except ImportError as exc:  # pragma: no cover - exercised only before install
    raise SystemExit("pypdf is required; install requirements.txt") from exc


GUIDELINES_URL = "https://infocom2027.ieee-infocom.org/submission-guidelines"
CFP_URL = "https://infocom2027.ieee-infocom.org/call-papers"
LETTER_WIDTH = 612.0
LETTER_HEIGHT = 792.0
SIZE_TOLERANCE = 1.0

SECRET_PATTERNS = (
    re.compile(rb"sk-[A-Za-z0-9_-]{20,}"),
    re.compile(rb"(?i)bearer\s+[A-Za-z0-9._~+/=-]{24,}"),
    re.compile(rb"eyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}"),
    re.compile(rb"(?i)yuangege\.cloud"),
)
INFRASTRUCTURE_BRAND_PATTERNS = (
    re.compile(rb"(?i)\bgpushare\b"),
)
LOCAL_PATH_PATTERN = re.compile(
    rb"(?i)(?:/Users/[A-Za-z0-9._-]+/|/home/[A-Za-z0-9._-]+/|[A-Z]:\\Users\\[A-Za-z0-9._-]+\\)"
)
EMAIL_PATTERN = re.compile(
    rb"(?i)\b[A-Z0-9._%+-]+@([A-Z0-9.-]+\.[A-Z]{2,})\b"
)
SAFE_EMAIL_DOMAINS = {
    "example.com",
    "example.net",
    "example.org",
    "attacker.com",
    "exfil.com",
}
SAFE_EMAIL_ADDRESSES = {
    "mark.black-2134@gmail.com",  # Public AgentDojo v1 synthetic task fixture.
}
FORBIDDEN_ARCHIVE_PREFIXES = (
    ".git/",
    "agent_replica/",
    "build/",
    "dist/",
    "external/",
    "output/",
    "paper/",
    "paper_writing/",
    "presentation/",
    "src/",
    "tmp/",
)
FORBIDDEN_ARCHIVE_FILES = {
    ".env",
    "runner/config.yaml",
}
REQUIRED_ARCHIVE_FILES = {
    "ANONYMIZATION.md",
    "ARTIFACT_MANIFEST.md",
    "README.md",
    "REPRODUCIBILITY.md",
    "analysis/independent_paired_outcomes.csv",
    "analysis/independent_unit_analysis.py",
    "analysis/http_commit_race_paired.csv",
    "analysis/http_commit_race_summary.csv",
    "analysis/audit_multiprocess_commit_race.py",
    "analysis/multiprocess_commit_race_detail.csv",
    "analysis/multiprocess_commit_race_summary.csv",
    "analysis/multiprocess_commit_race_paired.csv",
    "analysis/multiprocess_commit_race_audit_integrity.csv",
    "analysis/audit_commit_gateway_load.py",
    "analysis/commit_gateway_load_detail.csv",
    "analysis/commit_gateway_load_summary.csv",
    "analysis/audit_network_schedule.py",
    "analysis/analyze_network_schedule_results.py",
    "analysis/network_schedule_detail.csv",
    "analysis/network_schedule_summary.csv",
    "analysis/network_schedule_inference.csv",
    "analysis/network_schedule_by_family.csv",
    "analysis/network_schedule_paired.csv",
    "analysis/audit_async_queue_commit.py",
    "analysis/async_queue_commit_detail.csv",
    "analysis/async_queue_commit_summary.csv",
    "analysis/async_queue_commit_integrity.csv",
    "analysis/audit_docker_queue_failover.py",
    "analysis/make_figure1_v2.py",
    "analysis/docker_queue_failover_detail.csv",
    "analysis/docker_queue_failover_summary.csv",
    "analysis/docker_queue_failover_integrity.csv",
    "analysis/docker_queue_failover_metadata.csv",
    "analysis/audit_service_integrated_commit.py",
    "analysis/service_integrated_commit_detail.csv",
    "analysis/service_integrated_commit_summary.csv",
    "analysis/service_integrated_commit_integrity.csv",
    "analysis/audit_postgres_integrated_commit.py",
    "analysis/postgres_integrated_commit_detail.csv",
    "analysis/postgres_integrated_commit_summary.csv",
    "analysis/postgres_integrated_commit_integrity.csv",
    "analysis/postgres_integrated_commit_metadata.csv",
    "analysis/audit_container_commit_race.py",
    "analysis/container_commit_race_detail.csv",
    "analysis/container_commit_race_summary.csv",
    "analysis/container_commit_race_paired.csv",
    "analysis/container_commit_race_topology.csv",
    "analysis/container_commit_race_audit_integrity.csv",
    "analysis/audit_multihost_commit_race.py",
    "analysis/multihost_commit_race_detail.csv",
    "analysis/multihost_commit_race_summary.csv",
    "analysis/multihost_commit_race_paired.csv",
    "analysis/multihost_commit_race_topology.csv",
    "analysis/multihost_commit_race_audit_integrity.csv",
    "analysis/native_e2e48_attempt_audit.csv",
    "analysis/native_e2e48_final.jsonl",
    "analysis/native_e2e48_paired.csv",
    "analysis/native_e2e48_summary.csv",
    "analysis/summarize_native_e2e.py",
    "analysis/adaptive_native_fork_holdout_final.jsonl",
    "analysis/adaptive_native_fork_holdout_paired.csv",
    "analysis/adaptive_native_fork_holdout_summary.csv",
    "analysis/adaptive_native_fork_holdout_postrun_audit_by_boundary.csv",
    "analysis/adaptive_native_fork_holdout_postrun_audit_detail.csv",
    "analysis/adaptive_native_fork_holdout_postrun_audit_integrity.csv",
    "analysis/adaptive_native_fork_holdout_postrun_audit_ledger.csv",
    "analysis/adaptive_native_fork_holdout_postrun_audit_metadata.csv",
    "analysis/adaptive_native_fork_holdout_postrun_audit_paired.csv",
    "analysis/adaptive_native_fork_schema_neutral_final.jsonl",
    "analysis/adaptive_native_fork_schema_neutral_attempt_audit.csv",
    "analysis/adaptive_native_fork_schema_neutral_paired.csv",
    "analysis/adaptive_native_fork_schema_neutral_summary.csv",
    "analysis/adaptive_native_fork_schema_neutral_postrun_audit_by_boundary.csv",
    "analysis/adaptive_native_fork_schema_neutral_postrun_audit_detail.csv",
    "analysis/adaptive_native_fork_schema_neutral_postrun_audit_integrity.csv",
    "analysis/adaptive_native_fork_schema_neutral_postrun_audit_ledger.csv",
    "analysis/adaptive_native_fork_schema_neutral_postrun_audit_metadata.csv",
    "analysis/adaptive_native_fork_schema_neutral_postrun_audit_paired.csv",
    "analysis/adaptive_native_fork_schema_neutral_postrun_audit_provenance.csv",
    "analysis/adaptive_native_templates_detail.csv",
    "analysis/adaptive_native_templates_summary.csv",
    "analysis/analyze_adaptive_native_templates.py",
    "analysis/audit_adaptive_native_fork.py",
    "analysis/summarize_adaptive_native_fork.py",
    "analysis/audit_adaptive_effect_v2.py",
    "analysis/adaptive_effect_v2_detail.csv",
    "analysis/adaptive_effect_v2_summary.csv",
    "analysis/adaptive_effect_v2_integrity.csv",
    "analysis/audit_benchmark_oracle_capabilities.py",
    "analysis/benchmark_oracle_capability_audit.csv",
    "analysis/benchmark_oracle_capability_task_inventory.csv",
    "analysis/benchmark_oracle_capability_integrity.csv",
    "analysis/audit_official_oracle_distinguishability.py",
    "analysis/official_oracle_distinguishability_detail.csv",
    "analysis/official_oracle_distinguishability_summary.csv",
    "analysis/official_oracle_distinguishability_integrity.csv",
    "analysis/same_tool_native_commit_cluster_bootstrap.csv",
    "analysis/same_tool_native_commit_multiplicity.csv",
    "analysis/same_tool_native_commit_precision.csv",
    "requirements.txt",
    "runner/run_http_commit_race.py",
    "runner/run_multiprocess_commit_race.py",
    "runner/benchmark_commit_gateway_load.py",
    "runner/run_network_schedule_matrix.py",
    "runner/durable_async_queue.py",
    "runner/run_async_queue_commit.py",
    "runner/failover_queue.py",
    "runner/docker_failover_service.py",
    "runner/docker_failover_worker.py",
    "runner/run_docker_queue_failover.py",
    "runner/container_commit_service.py",
    "runner/run_container_commit_race.py",
    "runner/multihost_commit_service.py",
    "runner/run_multihost_commit_race.py",
    "runner/service_integrated_commit.py",
    "runner/run_service_integrated_commit.py",
    "runner/postgres_integrated_commit.py",
    "runner/run_postgres_integrated_commit.py",
    "runner/run_native_e2e.py",
    "runner/probe_native_tool_support.py",
    "runner/generate_adaptive_native_fork.py",
    "runner/run_adaptive_native_fork.py",
    "runner/strict_effects_v2.py",
    "scenarios/adaptive-native-holdout/MANIFEST.csv",
    "scenarios/adaptive-native-holdout/MANIFEST_SHA256.txt",
    "scenarios/native-e2e48/MANIFEST.csv",
    "scenarios/oracle-distinguishability/official_agentdojo_v1.json",
    "scripts/sanity_check.sh",
    "scripts/run_container_commit_race.sh",
    "scripts/run_multihost_commit_race.sh",
    "scripts/run_postgres_integrated_commit.sh",
    "tests/test_durable_async_queue.py",
    "tests/test_failover_queue.py",
    "tests/test_benchmark_oracle_capabilities.py",
    "tests/test_official_oracle_distinguishability.py",
    "tests/test_strict_effects_v2.py",
    "results/STAGE_SUMMARY_2026-07-30_INFOCOM_ORACLE_DISTINGUISHABILITY_PLAN.md",
    "results/STAGE_SUMMARY_2026-07-30_INFOCOM_ORACLE_DISTINGUISHABILITY_AMENDMENT.md",
    "results/STAGE_SUMMARY_2026-07-30_INFOCOM_ORACLE_DISTINGUISHABILITY_RESULT.md",
    "results/STAGE_SUMMARY_2026-07-31_INFOCOM_ORACLE_DISTINGUISHABILITY_HASH_AMENDMENT.md",
    "results/STAGE_SUMMARY_2026-07-20_INFOCOM_ASYNC_QUEUE_PLAN.md",
    "results/STAGE_SUMMARY_2026-07-20_INFOCOM_ASYNC_QUEUE_IMPLEMENTATION_FREEZE.md",
    "results/STAGE_SUMMARY_2026-07-20_INFOCOM_ASYNC_QUEUE_RESULT.md",
    "results/STAGE_SUMMARY_2026-07-20_INFOCOM_DOCKER_QUEUE_FAILOVER_PLAN.md",
    "results/STAGE_SUMMARY_2026-07-20_INFOCOM_DOCKER_QUEUE_FAILOVER_INFRA_FAILURE.md",
    "results/STAGE_SUMMARY_2026-07-20_INFOCOM_DOCKER_QUEUE_FAILOVER_AMENDMENT.md",
    "results/STAGE_SUMMARY_2026-07-20_INFOCOM_DOCKER_QUEUE_FAILOVER_IMPLEMENTATION_FREEZE.md",
    "results/STAGE_SUMMARY_2026-07-20_INFOCOM_DOCKER_QUEUE_FAILOVER_RESULT.md",
    "container/commit-race/Dockerfile",
    "container/commit-race/compose.yaml",
}


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    detail: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def compact(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def strip_tex_comments(value: str) -> str:
    return re.sub(r"(?m)(?<!\\)%.*$", "", value)


def tex_word_count(value: str) -> int:
    value = strip_tex_comments(value)
    previous = None
    while previous != value:
        previous = value
        value = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^]]*\])?\{([^{}]*)\}", r"\1", value)
    value = re.sub(r"\\[A-Za-z@]+\*?", " ", value)
    value = value.replace("--", "-").replace("~", " ")
    return len(re.findall(r"[A-Za-z0-9]+(?:['-][A-Za-z0-9]+)*", value))


def indirect_key(reference: Any, fallback: Any) -> tuple[Any, ...]:
    identifier = getattr(reference, "idnum", None)
    generation = getattr(reference, "generation", None)
    if identifier is not None:
        return (identifier, generation)
    return (id(fallback),)


def font_records(reader: PdfReader) -> list[tuple[str, str, bool]]:
    records: dict[tuple[Any, ...], tuple[str, str, bool]] = {}

    def visit(reference: Any) -> None:
        font = reference.get_object() if hasattr(reference, "get_object") else reference
        key = indirect_key(reference, font)
        if key in records:
            return
        subtype = str(font.get("/Subtype", "unknown"))
        name = str(font.get("/BaseFont", font.get("/Name", "unnamed")))
        embedded = subtype == "/Type3"
        descriptor_ref = font.get("/FontDescriptor")
        if descriptor_ref is not None:
            descriptor = descriptor_ref.get_object()
            embedded = any(
                item in descriptor for item in ("/FontFile", "/FontFile2", "/FontFile3")
            )
        records[key] = (name, subtype, embedded)
        for descendant in font.get("/DescendantFonts", []):
            visit(descendant)

    for page in reader.pages:
        resources_ref = page.get("/Resources")
        if resources_ref is None:
            continue
        resources = resources_ref.get_object()
        fonts_ref = resources.get("/Font")
        if fonts_ref is None:
            continue
        fonts = fonts_ref.get_object()
        for reference in fonts.values():
            visit(reference)
    return sorted(records.values())


def scan_sensitive_bytes(payload: bytes) -> tuple[int, int, int]:
    secret_count = sum(len(pattern.findall(payload)) for pattern in SECRET_PATTERNS)
    local_path_count = len(LOCAL_PATH_PATTERN.findall(payload))
    infrastructure_brand_count = sum(
        len(pattern.findall(payload)) for pattern in INFRASTRUCTURE_BRAND_PATTERNS
    )
    return secret_count, local_path_count, infrastructure_brand_count


def audit_pdf(pdf_path: Path) -> tuple[list[Check], dict[str, Any]]:
    checks: list[Check] = []
    facts: dict[str, Any] = {"path": str(pdf_path)}
    if not pdf_path.is_file():
        return [Check("pdf_exists", "FAIL", f"missing: {pdf_path}")], facts

    facts["sha256"] = sha256_file(pdf_path)
    facts["bytes"] = pdf_path.stat().st_size
    try:
        reader = PdfReader(str(pdf_path), strict=False)
    except Exception as exc:
        return [Check("pdf_readable", "FAIL", str(exc))], facts

    encrypted = bool(reader.is_encrypted)
    checks.append(Check("pdf_not_encrypted", "PASS" if not encrypted else "FAIL", str(encrypted)))
    page_count = len(reader.pages)
    facts["pages"] = page_count
    checks.append(
        Check(
            "page_limit",
            "PASS" if 1 <= page_count <= 10 else "FAIL",
            f"{page_count} pages; official maximum is 10 printed pages",
        )
    )

    sizes: list[tuple[float, float]] = []
    non_letter: list[int] = []
    texts: list[str] = []
    for index, page in enumerate(reader.pages, start=1):
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        rotation = int(page.get("/Rotate", 0)) % 360
        if rotation in (90, 270):
            width, height = height, width
        sizes.append((width, height))
        if abs(width - LETTER_WIDTH) > SIZE_TOLERANCE or abs(height - LETTER_HEIGHT) > SIZE_TOLERANCE:
            non_letter.append(index)
        texts.append(page.extract_text() or "")
    facts["page_sizes_points"] = sizes
    checks.append(
        Check(
            "letter_page_size",
            "PASS" if not non_letter else "FAIL",
            "all pages are 612 x 792 pt" if not non_letter else f"non-Letter pages: {non_letter}",
        )
    )

    sparse_pages = [index for index, value in enumerate(texts, start=1) if len(value.strip()) < 40]
    checks.append(
        Check(
            "text_searchable",
            "PASS" if not sparse_pages else "FAIL",
            "extractable text on every page" if not sparse_pages else f"sparse/unsearchable pages: {sparse_pages}",
        )
    )

    all_text = "\n".join(texts)
    compact_pages = [compact(value) for value in texts]
    reference_pages = [index for index, value in enumerate(compact_pages, start=1) if "references" in value]
    facts["references_start_page"] = reference_pages[0] if reference_pages else None
    main_text_ok = page_count <= 9 or bool(reference_pages and reference_pages[0] <= 10)
    checks.append(
        Check(
            "main_text_limit",
            "PASS" if main_text_ok else "FAIL",
            "total length is <=9 pages" if page_count <= 9 else f"references detected on page {reference_pages[0]}",
        )
    )

    metadata = {str(key): str(value) for key, value in (reader.metadata or {}).items()}
    facts["metadata"] = metadata
    author_metadata = metadata.get("/Author", "").strip()
    metadata_payload = "\n".join(metadata.values()).encode("utf-8", errors="ignore")
    metadata_secrets, metadata_paths, metadata_brands = scan_sensitive_bytes(metadata_payload)
    metadata_ok = (
        not author_metadata
        and not metadata_secrets
        and not metadata_paths
        and not metadata_brands
    )
    checks.append(
        Check(
            "anonymous_metadata",
            "PASS" if metadata_ok else "FAIL",
            "no author, credential, or local-path metadata"
            if metadata_ok
            else (
                f"author={author_metadata!r}, secrets={metadata_secrets}, "
                f"local_paths={metadata_paths}, infrastructure_brands={metadata_brands}"
            ),
        )
    )

    first_page_prefix = texts[0].split("Abstract", 1)[0] if texts else ""
    identity_pattern = re.compile(
        r"(?i)(?:\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b|\b(?:university|institute|department|affiliation|orcid)\b)"
    )
    identity_matches = identity_pattern.findall(first_page_prefix)
    checks.append(
        Check(
            "anonymous_title_block",
            "PASS" if not identity_matches else "FAIL",
            "no email or affiliation marker before the abstract"
            if not identity_matches
            else f"identity markers: {identity_matches}",
        )
    )

    font_info = font_records(reader)
    facts["fonts"] = [
        {"name": name, "subtype": subtype, "embedded": embedded}
        for name, subtype, embedded in font_info
    ]
    missing_fonts = [name for name, _, embedded in font_info if not embedded]
    checks.append(
        Check(
            "fonts_embedded",
            "PASS" if font_info and not missing_fonts else "FAIL",
            f"{len(font_info)} unique fonts, all embedded"
            if font_info and not missing_fonts
            else f"unembedded fonts: {missing_fonts or 'font resources not found'}",
        )
    )

    pdf_payload = pdf_path.read_bytes()
    text_payload = all_text.encode("utf-8", errors="ignore")
    raw_secrets, raw_paths, raw_brands = scan_sensitive_bytes(
        pdf_payload + b"\n" + text_payload
    )
    checks.append(
        Check(
            "no_credentials_or_local_paths",
            "PASS" if not raw_secrets and not raw_paths and not raw_brands else "FAIL",
            "no credential, local-path, or infrastructure-brand pattern in PDF bytes/text"
            if not raw_secrets and not raw_paths and not raw_brands
            else (
                f"secrets={raw_secrets}, local_paths={raw_paths}, "
                f"infrastructure_brands={raw_brands}"
            ),
        )
    )

    ai_pages = [
        index
        for index, value in enumerate(compact_pages, start=1)
        if "useofaidisclosure" in value
    ]
    ai_detail_markers = (
        "openaicodex",
        "softwaredevelopment",
        "inspectedbytheauthors",
        "validatedusingdeterministic",
    )
    compact_all = compact(all_text)
    ai_ok = bool(ai_pages and ai_pages[0] <= 9 and all(marker in compact_all for marker in ai_detail_markers))
    facts["ai_disclosure_page"] = ai_pages[0] if ai_pages else None
    checks.append(
        Check(
            "ai_disclosure",
            "PASS" if ai_ok else "FAIL",
            f"required titled disclosure begins on page {ai_pages[0]} and identifies use/validation"
            if ai_ok
            else "missing title in first 9 pages or required system/purpose/validation detail",
        )
    )
    return checks, facts


def read_tex_tree(source_path: Path) -> str:
    return "\n".join(
        path.read_text(encoding="utf-8", errors="replace")
        for path in sorted(source_path.parent.rglob("*.tex"))
    )


def audit_source(source_path: Path) -> tuple[list[Check], dict[str, Any]]:
    checks: list[Check] = []
    facts: dict[str, Any] = {"path": str(source_path)}
    if not source_path.is_file():
        return [Check("source_exists", "WARN", f"not checked: {source_path}")], facts

    main = strip_tex_comments(source_path.read_text(encoding="utf-8"))
    tree = strip_tex_comments(read_tex_tree(source_path))
    class_match = re.search(r"\\documentclass\s*\[([^]]+)\]\s*\{IEEEtran\}", main)
    options = set()
    if class_match:
        options = {item.strip().lower() for item in class_match.group(1).split(",")}
    required_options = {"10pt", "conference", "letterpaper"}
    class_ok = bool(class_match and required_options.issubset(options))
    checks.append(
        Check(
            "ieeetran_preamble",
            "PASS" if class_ok else "FAIL",
            f"IEEEtran options: {sorted(options)}",
        )
    )

    author_match = re.search(r"\\author\s*\{(.*?)\}", main, re.DOTALL)
    author_ok = bool(author_match is not None and not author_match.group(1).strip())
    checks.append(
        Check(
            "anonymous_source_author",
            "PASS" if author_ok else "FAIL",
            "empty \\author{}" if author_ok else "author block is absent or nonempty",
        )
    )

    acknowledgments = re.search(r"(?i)\\(?:section\*?|subsection\*?)\s*\{[^}]*acknow", tree)
    checks.append(
        Check(
            "no_acknowledgments",
            "PASS" if acknowledgments is None else "FAIL",
            "no acknowledgment section in review source",
        )
    )

    override_patterns = (
        r"\\usepackage(?:\[[^]]*\])?\{geometry\}",
        r"\\geometry\s*\{",
        r"\\linespread\s*\{",
        r"\\fontsize\s*\{",
        r"\\(?:setlength|addtolength)\s*\{\\(?:textwidth|textheight|oddsidemargin|evensidemargin|topmargin|columnsep|baselineskip)\}",
        r"\\renewcommand\s*\{\\baselinestretch\}",
    )
    used_overrides = [pattern for pattern in override_patterns if re.search(pattern, tree, re.I)]
    checks.append(
        Check(
            "no_template_overrides",
            "PASS" if not used_overrides else "FAIL",
            "no margin, font-size, or line-spacing override detected"
            if not used_overrides
            else f"matched {len(used_overrides)} override patterns",
        )
    )

    disclosures_path = source_path.parent / "sections" / "disclosures.tex"
    disclosure_text = (
        disclosures_path.read_text(encoding="utf-8", errors="replace")
        if disclosures_path.is_file()
        else ""
    )
    disclosure_included = bool(re.search(r"\\input\s*\{sections/disclosures\.tex\}", main))
    disclosure_title = bool(
        re.search(r"\\section\*?\s*\{Use of AI Disclosure\}", disclosure_text)
    )
    checks.append(
        Check(
            "ai_disclosure_source",
            "PASS" if disclosure_included and disclosure_title else "FAIL",
            "exactly titled disclosure is included in main.tex",
        )
    )

    abstract_path = source_path.parent / "sections" / "abstract.tex"
    abstract_words = None
    if abstract_path.is_file():
        abstract_words = tex_word_count(abstract_path.read_text(encoding="utf-8"))
    facts["abstract_words"] = abstract_words
    abstract_ok = abstract_words is not None and abstract_words <= 200
    checks.append(
        Check(
            "edas_ready_abstract",
            "PASS" if abstract_ok else "FAIL",
            f"{abstract_words} words; EDAS metadata limit is 200"
            if abstract_words is not None
            else "abstract source not found",
        )
    )

    build_log = source_path.parent.parent / "build" / "main.log"
    version = None
    if build_log.is_file():
        match = re.search(r"Document Class: IEEEtran .*?V(1\.8[a-z]?)", build_log.read_text(errors="replace"))
        version = match.group(1) if match else None
    facts["ieeetran_version"] = version
    checks.append(
        Check(
            "ieeetran_version",
            "PASS" if version and version.startswith("1.8") else "WARN",
            f"build log reports IEEEtran {version}" if version else "version not verified from build log",
        )
    )
    return checks, facts


def safe_fixture_email(match: re.Match[bytes]) -> bool:
    address = match.group(0).decode("ascii", errors="ignore").lower()
    domain = match.group(1).decode("ascii", errors="ignore").lower()
    # RFC 2606 reserves .test and .invalid for examples and negative tests.
    return (
        address in SAFE_EMAIL_ADDRESSES
        or domain in SAFE_EMAIL_DOMAINS
        or domain.endswith(".test")
        or domain.endswith(".invalid")
    )


def audit_artifact(artifact_path: Path) -> tuple[list[Check], dict[str, Any]]:
    checks: list[Check] = []
    facts: dict[str, Any] = {"path": str(artifact_path)}
    if not artifact_path.is_file():
        return [Check("artifact_exists", "FAIL", f"missing: {artifact_path}")], facts
    facts["sha256"] = sha256_file(artifact_path)
    facts["bytes"] = artifact_path.stat().st_size

    try:
        archive = zipfile.ZipFile(artifact_path)
    except (OSError, zipfile.BadZipFile) as exc:
        return [Check("artifact_zip_readable", "FAIL", str(exc))], facts

    with archive:
        bad_paths: list[str] = []
        symlinks: list[str] = []
        forbidden: list[str] = []
        secret_files: list[str] = []
        local_path_files: list[str] = []
        infrastructure_brand_files: list[str] = []
        identity_email_files: list[str] = []
        names = set()
        for info in archive.infolist():
            name = info.filename
            names.add(name)
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or "\\" in name:
                bad_paths.append(name)
            mode = (info.external_attr >> 16) & 0xFFFF
            if stat.S_ISLNK(mode):
                symlinks.append(name)
            lower = name.lower()
            basename = path.name.lower()
            secret_filename = basename.startswith(".env") or path.suffix.lower() in {
                ".key",
                ".pem",
                ".token",
                ".log",
                ".sqlite",
                ".sqlite3",
                ".db",
            }
            local_runtime_file = basename.startswith("screenlog")
            local_runner_config = lower.startswith("runner/config.") and lower != (
                "runner/config.example.yaml"
            )
            if (
                lower in FORBIDDEN_ARCHIVE_FILES
                or secret_filename
                or local_runtime_file
                or local_runner_config
                or any(lower.startswith(prefix) for prefix in FORBIDDEN_ARCHIVE_PREFIXES)
            ):
                forbidden.append(name)
            if info.is_dir():
                continue
            payload = archive.read(info)
            secrets, local_paths, infrastructure_brands = scan_sensitive_bytes(payload)
            if secrets:
                secret_files.append(name)
            if local_paths:
                local_path_files.append(name)
            if infrastructure_brands:
                infrastructure_brand_files.append(name)
            emails = list(EMAIL_PATTERN.finditer(payload))
            if any(not safe_fixture_email(match) for match in emails):
                identity_email_files.append(name)

        facts["entries"] = len(archive.infolist())
        facts["uncompressed_bytes"] = sum(info.file_size for info in archive.infolist())
        required_missing = sorted(REQUIRED_ARCHIVE_FILES - names)
        checks.append(
            Check(
                "artifact_structure",
                "PASS" if not bad_paths and not symlinks else "FAIL",
                f"{len(names)} entries; no unsafe paths or symlinks"
                if not bad_paths and not symlinks
                else f"unsafe_paths={bad_paths}, symlinks={symlinks}",
            )
        )
        checks.append(
            Check(
                "artifact_scope",
                "PASS" if not forbidden and not required_missing else "FAIL",
                "required public files present; paper/build/config/git paths absent"
                if not forbidden and not required_missing
                else f"forbidden={forbidden[:10]}, missing={required_missing}",
            )
        )
        checks.append(
            Check(
                "artifact_sensitive_data",
                "PASS"
                if not secret_files
                and not local_path_files
                and not infrastructure_brand_files
                and not identity_email_files
                else "FAIL",
                "no credential, machine path, infrastructure brand, or non-fixture email"
                if not secret_files
                and not local_path_files
                and not infrastructure_brand_files
                and not identity_email_files
                else (
                    f"secrets={secret_files[:10]}, local_paths={local_path_files[:10]}, "
                    f"infrastructure_brands={infrastructure_brand_files[:10]}, "
                    f"emails={identity_email_files[:10]}"
                ),
            )
        )
    return checks, facts


def print_section(title: str, checks: Iterable[Check]) -> None:
    print(f"\n{title}")
    for check in checks:
        print(f"[{check.status}] {check.name}: {check.detail}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit INFOCOM 2027 PDF/source and optional anonymous artifact"
    )
    parser.add_argument(
        "--pdf",
        type=Path,
        default=Path("output/pdf/PSEBench_INFOCOM2027_submission_draft.pdf"),
    )
    parser.add_argument("--source", type=Path, default=Path("src/main.tex"))
    parser.add_argument("--artifact", type=Path)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()

    pdf_checks, pdf_facts = audit_pdf(args.pdf)
    source_checks, source_facts = audit_source(args.source)
    sections: list[tuple[str, list[Check]]] = [
        ("PDF", pdf_checks),
        ("SOURCE", source_checks),
    ]
    report: dict[str, Any] = {
        "official_sources": {"guidelines": GUIDELINES_URL, "cfp": CFP_URL},
        "pdf": {"facts": pdf_facts, "checks": [asdict(item) for item in pdf_checks]},
        "source": {
            "facts": source_facts,
            "checks": [asdict(item) for item in source_checks],
        },
    }
    if args.artifact is not None:
        artifact_checks, artifact_facts = audit_artifact(args.artifact)
        sections.append(("ARTIFACT", artifact_checks))
        report["artifact"] = {
            "facts": artifact_facts,
            "checks": [asdict(item) for item in artifact_checks],
        }

    all_checks = [check for _, checks in sections for check in checks]
    for title, checks in sections:
        print_section(title, checks)
    counts = {status: sum(item.status == status for item in all_checks) for status in ("PASS", "WARN", "FAIL")}
    print(f"\nSUMMARY: {counts['PASS']} pass, {counts['WARN']} warn, {counts['FAIL']} fail")
    if pdf_facts.get("sha256"):
        print(f"PDF SHA-256: {pdf_facts['sha256']}")
    artifact = report.get("artifact", {}).get("facts", {})
    if artifact.get("sha256"):
        print(f"ARTIFACT SHA-256: {artifact['sha256']}")

    report["summary"] = counts
    if args.json_output is not None:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 1 if counts["FAIL"] else 0


if __name__ == "__main__":
    sys.exit(main())
