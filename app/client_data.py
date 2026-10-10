COMPANY_SIZES = ["1-10", "11-50", "51-200", "201-500", "501-1000", "1000+"]
AGREEMENT_TYPES = ["Client Services Agreement", "Recruitment Agreement", "Other"]

CLIENT_STATUS_LABELS = {
    "NEW": "New", "UNDER_REVIEW": "Under review", "APPROVED": "Approved", "AGREEMENT_PENDING": "Agreement pending",
    "AGREEMENT_SENT": "Agreement sent", "AGREEMENT_ACCEPTED": "Agreement accepted", "ACTIVE": "Active",
    "SUSPENDED": "Suspended", "EXPIRED": "Expired", "REJECTED": "Rejected",
}
AGREEMENT_STATUS_LABELS = {
    "NOT_REQUIRED": "Not required", "PENDING": "Pending", "SENT": "Sent", "VIEWED": "Viewed",
    "ACCEPTED": "Accepted", "DECLINED": "Declined", "EXPIRED": "Expired",
}


CLIENT_STEPS = ["Registered", "Under review", "Agreement", "Active", "Hiring"]
_CLIENT_STEP_OF_STATUS = {
    "NEW": 1, "UNDER_REVIEW": 1, "APPROVED": 2, "AGREEMENT_PENDING": 2, "AGREEMENT_SENT": 2,
    "AGREEMENT_ACCEPTED": 2, "ACTIVE": 3,
}


def client_progress(status, has_jobs=False):
    index = _CLIENT_STEP_OF_STATUS.get(status)
    if index == 3 and has_jobs:
        index = 4
    return (CLIENT_STEPS, index) if index is not None else (None, None)
