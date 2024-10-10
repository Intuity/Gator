from typing import Dict, List, Optional, TypedDict


class Summary(TypedDict):
    metrics: Dict[str, int]
    sub_total: int
    sub_active: int
    sub_passed: int
    sub_failed: int
    failed_ids: List[List[str]]


def make_summary(
    metrics: Optional[Dict[str, int]] = None,
    sub_total: int = 0,
    sub_active: int = 0,
    sub_passed: int = 0,
    sub_failed: int = 0,
    failed_ids: Optional[List[List[str]]] = None,
):
    return Summary(
        sub_total=sub_total,
        sub_active=sub_active,
        sub_passed=sub_passed,
        sub_failed=sub_failed,
        failed_ids=failed_ids or [],
        metrics=metrics or {},
    )


def contextualise_summary(context: str, summary: Summary):
    new_summary = make_summary(**summary)
    new_summary["failed_ids"] = [[context, *x] for x in summary["failed_ids"]]
    return new_summary


def merge_summaries(*summaries: Summary, base: Optional[Summary] = None):
    if base is None:
        base = make_summary()
    for summary in summaries:
        for m_key, m_val in summary["metrics"].items():
            base["metrics"][m_key] = base["metrics"].get(m_key, 0) + m_val
        base["sub_total"] += summary["sub_total"]
        base["sub_active"] += summary["sub_active"]
        base["sub_passed"] += summary["sub_passed"]
        base["sub_failed"] += summary["sub_failed"]
        base["failed_ids"] += summary["failed_ids"]
    return base
