from __future__ import annotations

import re

# Lower score means higher legal authority in conflict comparison.
LEGAL_TYPE_RANK = {
    "hien_phap": 1,
    "bo_luat": 2,
    "luat": 3,
    "nghi_quyet": 4,
    "nghi_dinh": 5,
    "quyet_dinh": 6,
    "thong_tu": 7,
    "cong_van": 8,
    "khac": 9,
}


def detect_legal_type(title: str) -> str:
    t = (title or "").lower()

    if re.search(r"\bhien\s*phap\b", t):
        return "hien_phap"
    if re.search(r"\bbo\s*luat\b", t):
        return "bo_luat"
    if re.search(r"\bluat\b", t):
        return "luat"
    if re.search(r"\bnghi\s*quyet\b", t):
        return "nghi_quyet"
    if re.search(r"\bnghi\s*dinh\b", t):
        return "nghi_dinh"
    if re.search(r"\bquyet\s*dinh\b", t):
        return "quyet_dinh"
    if re.search(r"\bthong\s*tu\b", t):
        return "thong_tu"
    if re.search(r"\bcong\s*van\b", t):
        return "cong_van"
    return "khac"


def legal_priority(title: str) -> int:
    return LEGAL_TYPE_RANK[detect_legal_type(title)]
