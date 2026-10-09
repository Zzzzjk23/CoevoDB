"""Bounds for one plan or data probe.

The corpus report must not include timings, so these stay out of its JSON.
"""

# A referenced table larger than this is not inspected: the data layer is
# unavailable rather than silently truncated. Set-operation inputs use the
# same cap and, past it, contribute no features.
MAX_TABLE_ROWS = 10_000

# Wall-clock budget for one probe statement. DuckDB honours it; DataFusion's
# runner accepts the argument and does not interrupt.
PROBE_TIMEOUT_S = 10.0

# Default budget for one isolated phi extraction, child process included.
ISOLATION_TIMEOUT_S = 60.0
