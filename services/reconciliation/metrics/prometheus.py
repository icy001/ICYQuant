from prometheus_client import Counter, Histogram


RECONCILIATION_TOTAL = Counter(
    "icyquant_reconciliation_total",
    "Total reconciliation runs",
)

MISMATCH_TOTAL = Counter(
    "icyquant_mismatch_total",
    "Total mismatches detected",
)

REPAIR_SUCCESS_TOTAL = Counter(
    "icyquant_repair_success_total",
    "Total successful repairs",
)

REPAIR_FAILED_TOTAL = Counter(
    "icyquant_repair_failed_total",
    "Total failed repairs",
)

REPLAY_LATENCY = Histogram(
    "icyquant_replay_latency",
    "Replay latency in seconds",
    buckets=[0.1, 0.5, 1.0, 5.0, 10.0],
)
