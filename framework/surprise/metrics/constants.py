"""Constants for the per-run metrics. The S11 gate pins these values."""

from __future__ import annotations

# Surprise, in bits, at or above which an execution counts as high-surprise.
HIGH_SURPRISE_BITS = 4.0

# Bin edges for the calibration curve; the last interval is closed on the right.
CALIBRATION_EDGES = (0.0, 0.05, 0.2, 0.4, 0.6, 0.8, 0.95, 1.0)

# Most generations kept as rows and columns of a CIAO matrix.
CIAO_MAX_GENERATIONS = 12

# Most records taken from one generation's batch when building a CIAO matrix.
CIAO_BATCH_SAMPLE = 200

# Default width, in executions, of one point on the surprise curve.
CURVE_WINDOW = 100

# A tooth must rise and then fall by at least this many bits.
TEETH_AMPLITUDE = 0.25

# How many curve points on each side of a candidate tooth are inspected.
TEETH_WIDTH = 5


def as_dict() -> dict:
    """The seven constants above. Tuples stay tuples."""
    return {
        "HIGH_SURPRISE_BITS": HIGH_SURPRISE_BITS,
        "CALIBRATION_EDGES": CALIBRATION_EDGES,
        "CIAO_MAX_GENERATIONS": CIAO_MAX_GENERATIONS,
        "CIAO_BATCH_SAMPLE": CIAO_BATCH_SAMPLE,
        "CURVE_WINDOW": CURVE_WINDOW,
        "TEETH_AMPLITUDE": TEETH_AMPLITUDE,
        "TEETH_WIDTH": TEETH_WIDTH,
    }
