"""Bounds for one plan or data probe.

The corpus report must not include timings, so these stay out of its JSON.
"""

# A referenced table larger than this is not inspected: the data layer is
# unavailable rather than silently truncated. A set-operation input that runs
# on its own and passes this cap makes the data layer unavailable too. An
# input that cannot run on its own contributes no features.
MAX_TABLE_ROWS = 10_000

# Wall-clock budget for one probe statement. DuckDB honours it; DataFusion's
# runner accepts the argument and does not interrupt.
PROBE_TIMEOUT_S = 10.0

# Default budget for one isolated phi extraction, child process included.
ISOLATION_TIMEOUT_S = 60.0
