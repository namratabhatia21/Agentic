from datetime import UTC, datetime

import pytest

pytest.importorskip("azure.storage.blob")

from ingest.parsers import parse  # noqa: E402
from ingest.pipeline import _to_csv, index_names  # noqa: E402
from ingest.schemas import SPECS, DocType, record_text  # noqa: E402


def test_parse_csv_normalizes_headers():
    rows = parse("x.csv", b"ID,Problem Description,Root Cause\n1,leak,seal\n,,\n")
    assert rows == [{"id": "1", "problem_description": "leak", "root_cause": "seal"}]


def test_parse_rejects_unknown_type():
    with pytest.raises(ValueError):
        parse("x.pdf", b"...")


def test_index_names_versioned():
    n = index_names(DocType.CQ, datetime(2026, 10, 2, tzinfo=UTC), "versioned")
    assert n["elasticsearch_index"] == "cq-20261002"
    assert n["azure_search_index"] == "cq-idx-20261002"
    assert n["elasticsearch_alias"] == "cq-current"


def test_record_text_uses_spec_fields():
    t = record_text(SPECS[DocType.EIGHT_D], {"id": "1", "root_cause": "seal", "x": "y"})
    assert t == "root_cause: seal"


def test_summary_csv_skips_embeddings():
    out = _to_csv([{"record_id": "1", "summary": "s", "embedding": [0.1]}]).decode()
    assert out.splitlines()[0] == "record_id,summary"
