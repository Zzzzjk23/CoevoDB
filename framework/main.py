"""Forwarder: the old CoevoDB main loop now lives in surprise/baselines/coevodb_v1/main.py (moved in S12)."""
import runpy

if __name__ == "__main__":
    runpy.run_module("surprise.baselines.coevodb_v1.main", run_name="__main__", alter_sys=True)
