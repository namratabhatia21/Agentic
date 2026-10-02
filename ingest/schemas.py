"""Per-document-type definitions: ID field, text fields to summarize, index prefix."""

from dataclasses import dataclass
from enum import StrEnum


class DocType(StrEnum):
    EIGHT_D = "8d"
    REXM = "rexm"
    CQ = "cq"


@dataclass(frozen=True)
class DocSpec:
    prefix: str
    id_field: str
    text_fields: tuple[str, ...]
    summary_prompt: str


# Field names are matched case-insensitively against the uploaded file's headers.
# Adjust them to match the real 8D / RexMCards / CQ exports.
SPECS: dict[DocType, DocSpec] = {
    DocType.EIGHT_D: DocSpec(
        prefix="8d",
        id_field="id",
        text_fields=("title", "problem_description", "root_cause", "corrective_action"),
        summary_prompt="Summarize this 8D problem-solving report: problem, root cause, "
        "corrective and preventive actions.",
    ),
    DocType.REXM: DocSpec(
        prefix="rexm",
        id_field="id",
        text_fields=("title", "description", "lesson_learned"),
        summary_prompt="Summarize this RexM card (return-of-experience): the event, "
        "its cause and the lesson learned.",
    ),
    DocType.CQ: DocSpec(
        prefix="cq",
        id_field="id",
        text_fields=("title", "question", "change_request", "answer"),
        summary_prompt="Summarize this Clear Question / Change Request: what is asked or "
        "changed, why, and the decision.",
    ),
}


def record_text(spec: DocSpec, record: dict) -> str:
    parts = [f"{f}: {record[f]}" for f in spec.text_fields if record.get(f)]
    return "\n".join(parts) if parts else "\n".join(f"{k}: {v}" for k, v in record.items() if v)
