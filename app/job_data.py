from .talent_data import AVAILABILITY

WORK_MODES = ["Remote", "Hybrid", "Onsite"]
CONTRACT_TYPES = AVAILABILITY[:3]  # Full-time, Part-time, Contract / project-based
CURRENCIES = ["USD", "NGN", "EUR", "GBP"]

JOB_STATUS_LABELS = {
    "DRAFT": "Draft", "SUBMITTED": "Submitted", "REVIEWING": "Reviewing", "MATCHING": "Matching",
    "SHORTLISTED": "Shortlisted", "INTERVIEWING": "Interviewing", "FILLED": "Filled", "CLOSED": "Closed",
}
MATCH_STATUS_LABELS = {
    "SUGGESTED": "Suggested", "SHORTLISTED": "Shortlisted", "PRESENTED": "Presented to client",
    "INTERVIEWING": "Interview", "PLACED": "Placed", "REJECTED": "Closed",
}
SCORE_NOTE = "Internal matching score \u2014 not a guarantee of suitability or hiring."
