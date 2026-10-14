"""Fixed values for the S8 gate (data only; ``gates/all.py`` does not run this file).

The Hunter and Diagnoser constants are pinned here the same way the S6 and S7
gates pin the theory constants. ``BETA`` is not: PLAN decision 8 says beta is
tuned once on independent seeds and then frozen, so its value is pinned by the
pre-experiment record in ``s08_runs.json`` (written by the orchestrator after
the pre-experiment, together with the digests of the long-run artifacts).
"""
from __future__ import annotations

ORACLES = ("tlp", "norec", "plan_variant", "index_presence", "equivalent_query", "version_differential", "cross_dbms")
LANES = ("refine", "generalize", "migrate", "explore")

HUNTER_CONSTANTS = {
    "EXPLORE_SEEDS_PER_STEP": 6,
    "SEED_MUTATIONS_PER_SEED": 1,
    "PARENTS_PER_HYPOTHESIS": 3,
    "MUTANTS_PER_STEP": 48,
    "MIGRATE_PER_STEP": 8,
    "EXPLORE_EVERY": 5,
    "PROBE_HALF": 50.0,
    "NOVELTY_WINDOW": 200,
    "NOVELTY_FLOOR": 0.2,
    "ADJACENT_FACTOR": 2.0,
    "PHI_TIMEOUT_S": 30.0,
    "EMPTY_ROUNDS": 20,
}
DIAGNOSER_CONSTANTS = {"COMPRESS_EVERY": 100, "CHECKPOINT_EVERY": 100}

# The pre-experiment that fixes BETA (PLAN decision 8; DECISIONS, S8).
BETA_CANDIDATES = (0.5, 1.0, 2.0, 4.0)
PRE_SEEDS = (9001, 9002, 9003)
PRE_EXPERIMENTS = 300

# Known reproductions fed first by the short runs (names of gates/s04_cases.CASES).
BOOTSTRAP = (("F1", "plan_variant"), ("DF-A", "cross_dbms"))

CANDIDATES_SEED = 11
LANES_RUN = {"seed": 21, "experiments": 30, "engines": ("duckdb", "datafusion")}
DETERMINISM_RUN = {"seed": 31, "other_seed": 32, "experiments": 25, "engines": ("duckdb",)}

# Artifact checks.
LONGRUN = {"min_minutes": 120.0, "min_records": 1000, "max_harness_error": 0.01, "engines": ("duckdb",)}
SAWTOOTH = {"window": 100, "amplitude": 0.25, "width": 5, "min_teeth": 3}
DUPLICATES = {"budget_tolerance": 0.10, "min_old_reports": 2}
# Known bugs for the DuckDB 1.1.3 recall report: the DuckDB confirmed families of the M1 table.
RECALL_CASES = ("F1", "F2", "F2_file", "F7", "F7_file", "F9", "F11", "F6", "F6_predicate")

# Hand-computed values for the scoring group.
# optimistic_rate(tested, unexplained) = min(0.5, rho + sqrt(rho (1 - rho) / (tested + 1))), rho = (u + 1) / (t + 100)
OPTIMISTIC = {
    (0, 0): 0.01 + (0.01 * 0.99) ** 0.5,
    (99, 0): 1 / 199 + ((1 / 199) * (198 / 199) / 100) ** 0.5,
    (10, 10): 0.1 + (0.1 * 0.9 / 11) ** 0.5,
    (100, 100): 0.5,
}
