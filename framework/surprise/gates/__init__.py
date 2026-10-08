"""Session gates: one ``sNN.py`` per session, exit code 0 = pass.

Run everything from ``framework/`` with ``python -m surprise.gates.all``.
Gates are written by the orchestrator before a session's work packages are
dispatched; executors never edit this package.
"""
