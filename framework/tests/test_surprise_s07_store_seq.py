"""The journal sequence is cached on the store that has the directory open."""

from __future__ import annotations

import surprise.theory.store as store_module
from surprise.theory import TheoryStore


def test_appends_do_not_reread_the_journal_and_reopen_continues(tmp_path, monkeypatch):
    root = tmp_path / "store"
    created = TheoryStore.create(root)
    assert created.last_seq == 0
    assert created.append_journal({"kind": "observe", "record_id": "r1"}) == 1
    assert created.append_journal({"kind": "observe", "record_id": "r2"}) == 2
    assert created.last_seq == 2

    opened = TheoryStore.open(root)
    assert opened.last_seq == 2
    calls = {"n": 0}
    original = store_module._read_jsonl

    def counting(path, label):
        calls["n"] += 1
        return original(path, label)

    monkeypatch.setattr(store_module, "_read_jsonl", counting)
    assert opened.last_seq == 2
    assert opened.append_journal({"kind": "observe", "record_id": "r3"}) == 3
    closed = opened.close_generation(opened.load(), cause="checkpoint:batch")
    assert closed == 0
    assert opened.append_journal({"kind": "observe", "record_id": "r4"}) == 4
    assert opened.append_journal({"kind": "checkpoint", "note": "next"}) == 5
    assert calls["n"] == 0
    assert opened.last_seq == 5
    assert [row["seq"] for row in opened.journal()] == [1, 2, 3, 4, 5]
    assert calls["n"] == 1

    fresh = TheoryStore.open(root)
    assert fresh.last_seq == 5
    assert fresh.append_journal({"kind": "observe", "record_id": "r5"}) == 6
    assert [row["seq"] for row in fresh.journal()] == [1, 2, 3, 4, 5, 6]
