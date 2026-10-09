"""Saving a theory: one file per hypothesis, append-only logs, generation snapshots."""

from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from surprise.harness.contracts import Label
from surprise.theory import StoreError, Theory, TheoryEdit, TheoryStore

from test_surprise_s06_common import (
    INT_ALL,
    L_DUPS,
    PLAIN,
    S_HAND,
    SELECT,
    SET_ALL,
    X1,
    X3,
    hypothesis,
    phi,
)


ORACLE = "cross_dbms"


def _pass(oracle: str = ORACLE) -> Label:
    return Label(y="pass", oracle=oracle)


def _invalid() -> Label:
    return Label(y="invalid", oracle=ORACLE, invalid_reason="query_error")


def _populated() -> Theory:
    theory = Theory()
    theory.put(hypothesis(hypothesis_id="h-a", specific=S_HAND, general=((L_DUPS,),)))
    theory.put(
        hypothesis(
            hypothesis_id="h-b",
            specific=(INT_ALL, L_DUPS),
            general=((L_DUPS,),),
            behavior_shape="extra_only",
        )
    )
    theory.observe(phi(PLAIN), _pass(), "p1")
    theory.observe(phi(X3), _pass(), "p2")
    theory.observe(phi(X1), _invalid(), "i1")
    return theory


def _files(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in root.rglob("*")
        if path.is_file()
    }


def _read(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, data: object) -> None:
    path.write_text(
        json.dumps(data, sort_keys=True, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _edit(theory: Theory, edit_id: str = "e1", decision: str = "accepted") -> TheoryEdit:
    return TheoryEdit(
        edit_id=edit_id,
        kind="revise",
        rationale="why",
        bets=({"spec": {"engine": "datafusion", "oracle": ORACLE}, "expect": "fail"},),
        surprise_delta_in=-1.0,
        surprise_delta_out=0.0,
        decision=decision,
        proposer="hand",
        theory_version=theory.version,
        payload={"adds": ["h9"]},
    )


def test_a_new_store_is_empty_and_will_not_be_created_twice(tmp_path: Path) -> None:
    assert issubclass(StoreError, ValueError)
    root = tmp_path / "store"
    store = TheoryStore.create(root)
    assert store.root == root
    assert store.last_seq == 0
    assert store.load().to_dict() == Theory().to_dict()
    assert store.journal() == []
    assert store.edits() == []
    assert store.edit_history() == []
    assert store.negatives() == []
    assert store.generations() == []
    assert store.verify() == []
    head = store.head()
    assert head["schema"] == 1
    assert head["generation"] == 0
    assert head["hypotheses"] == []
    assert head["version"] == Theory().version
    assert (root / "hypotheses").is_dir()
    assert (root / "passes").is_dir()
    assert (root / "generations").is_dir()
    assert (root / "journal.jsonl").read_bytes() == b""
    empty = tmp_path / "empty"
    empty.mkdir()
    assert TheoryStore.create(empty).load().to_dict() == Theory().to_dict()
    with pytest.raises(StoreError):
        TheoryStore.create(root)
    with pytest.raises(StoreError):
        TheoryStore.open(tmp_path / "nowhere")


def test_save_and_load_round_trip_and_drop_files_that_left(tmp_path: Path) -> None:
    theory = _populated()
    store = TheoryStore.create(tmp_path / "store")
    store.save(theory)
    root = store.root
    names = sorted(path.name for path in (root / "hypotheses").iterdir())
    assert names == sorted(f"{item.hypothesis_id}.json" for item in theory.hypotheses)
    for item in theory.hypotheses:
        assert _read(root / "hypotheses" / f"{item.hypothesis_id}.json") == item.to_dict()
    assert any((root / "passes").glob("*.jsonl"))
    opened = TheoryStore.open(root)
    loaded = opened.load()
    assert loaded.to_dict() == theory.to_dict()
    assert loaded.version == theory.version
    assert loaded.predict(phi(X1), ORACLE).to_dict() == theory.predict(phi(X1), ORACLE).to_dict()
    assert not list(root.rglob("*.tmp"))
    for path in root.rglob("*"):
        if path.is_file():
            assert b"\r" not in path.read_bytes()
    smaller = Theory.from_dict(theory.to_dict())
    removed = smaller.hypotheses[0].hypothesis_id
    smaller.remove(removed)
    store.save(smaller)
    assert not (root / "hypotheses" / f"{removed}.json").exists()
    assert store.load().to_dict() == smaller.to_dict()
    cleared = Theory.from_dict({**theory.to_dict(), "passes": {}})
    store.save(theory)
    assert list((root / "passes").glob("*.jsonl"))
    store.save(cleared)
    assert list((root / "passes").glob("*.jsonl")) == []
    assert store.load().to_dict() == cleared.to_dict()


def test_an_unchanged_save_does_not_rewrite(tmp_path: Path) -> None:
    theory = _populated()
    store = TheoryStore.create(tmp_path / "store")
    store.save(theory)
    path = store.root / "head.json"
    os.utime(path, ns=(1_000_000_000, 1_000_000_000))
    store.save(theory)
    assert path.stat().st_mtime_ns == 1_000_000_000
    assert not list(store.root.rglob("*.tmp"))


def test_a_refused_save_writes_nothing(tmp_path: Path) -> None:
    theory = _populated()
    store = TheoryStore.create(tmp_path / "store")
    store.save(theory)
    before = _files(tmp_path)
    for bad in ("../escape", "a/b", "a\\b", ".hidden", "x" * 80, "con:1"):
        odd = Theory.from_dict(theory.to_dict())
        odd.put(hypothesis(hypothesis_id=bad, specific=(SELECT,), general=((SELECT,),)))
        with pytest.raises(StoreError):
            store.save(odd)
    odd = Theory.from_dict(theory.to_dict())
    odd.put(hypothesis(hypothesis_id="h-ok", engine="a/b", specific=(SELECT,), general=((SELECT,),)))
    with pytest.raises(StoreError):
        store.save(odd)
    assert _files(tmp_path) == before
    assert store.load().to_dict() == theory.to_dict()
    long_id = "h" + "1" * 63
    accepted = Theory.from_dict(theory.to_dict())
    accepted.put(hypothesis(hypothesis_id=long_id, specific=(SELECT,), general=((SELECT,),)))
    store.save(accepted)
    assert (store.root / "hypotheses" / f"{long_id}.json").is_file()
    with pytest.raises(StoreError):
        longer = Theory.from_dict(theory.to_dict())
        longer.put(hypothesis(hypothesis_id="h" + "1" * 64, specific=(SELECT,), general=((SELECT,),)))
        store.save(longer)
    assert store.load().to_dict() == accepted.to_dict()


def _copy(source: Path, dest: Path) -> Path:
    shutil.copytree(source, dest)
    return dest


def test_load_refuses_a_store_that_is_not_canonical(tmp_path: Path) -> None:
    theory = _populated()
    store = TheoryStore.create(tmp_path / "store")
    store.save(theory)
    first = theory.hypotheses[0].hypothesis_id
    second = theory.hypotheses[1].hypothesis_id

    def edit(relative: str, change) -> None:
        path = root / relative
        _write(path, change(_read(path)))

    cases: list[tuple[str, object]] = []

    root = _copy(store.root, tmp_path / "missing")
    (root / "hypotheses" / f"{first}.json").unlink()
    cases.append(("missing", root))

    root = _copy(store.root, tmp_path / "stray")
    shutil.copyfile(root / "hypotheses" / f"{first}.json", root / "hypotheses" / "h99.json")
    cases.append(("stray", root))

    root = _copy(store.root, tmp_path / "other-id")
    edit(f"hypotheses/{first}.json", lambda data: {**data, "hypothesis_id": second})
    cases.append(("other-id", root))

    root = _copy(store.root, tmp_path / "not-json")
    (root / "hypotheses" / f"{first}.json").write_text("{", encoding="utf-8")
    cases.append(("not-json", root))

    root = _copy(store.root, tmp_path / "bad-hypothesis")
    edit(f"hypotheses/{first}.json", lambda data: {key: value for key, value in data.items() if key != "status"})
    cases.append(("bad-hypothesis", root))

    root = _copy(store.root, tmp_path / "unsorted")

    def swap(data: dict) -> dict:
        specific = list(reversed(data["specific"]))
        assert specific != data["specific"]
        return {**data, "specific": specific}

    edit(f"hypotheses/{first}.json", swap)
    cases.append(("unsorted", root))

    root = _copy(store.root, tmp_path / "ancestor")
    edit(
        f"hypotheses/{first}.json",
        lambda data: {**data, "specific": [SET_ALL, *data["specific"]]},
    )
    cases.append(("ancestor", root))

    root = _copy(store.root, tmp_path / "duplicate-pass")
    path = next((root / "passes").iterdir())
    text = path.read_text(encoding="utf-8")
    path.write_text(text + text.split("\n")[0] + "\n", encoding="utf-8", newline="\n")
    cases.append(("duplicate-pass", root))

    root = _copy(store.root, tmp_path / "foreign-pass")
    path = next((root / "passes").iterdir())
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").split("\n") if line]
    rows[0]["phi"]["vocab"] = "0" * 64
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
        newline="\n",
    )
    cases.append(("foreign-pass", root))

    root = _copy(store.root, tmp_path / "bad-phi")
    path = next((root / "passes").iterdir())
    path.write_text(
        json.dumps({"phi": {}, "record_id": "x"}, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    cases.append(("bad-phi", root))

    root = _copy(store.root, tmp_path / "bad-residual")
    edit("residual.json", lambda data: {**data, "u": {"tested": 1, "unexplained": 2}})
    cases.append(("bad-residual", root))

    root = _copy(store.root, tmp_path / "bad-validity")
    edit(
        "validity.json",
        lambda data: {"made-up": {"cross_dbms": {"tested": 1, "invalid": 2, "reasons": {}}}},
    )
    cases.append(("bad-validity", root))

    root = _copy(store.root, tmp_path / "next-id")
    edit("head.json", lambda data: {**data, "next_id": data["next_id"] + 5})
    cases.append(("next-id", root))

    root = _copy(store.root, tmp_path / "reordered")
    edit("head.json", lambda data: {**data, "hypotheses": list(reversed(data["hypotheses"]))})
    cases.append(("reordered", root))

    seen = set()
    for name, damaged in cases:
        seen.add(name)
        with pytest.raises(StoreError) as raised:
            TheoryStore.open(damaged).load()
        assert damaged.name in str(raised.value) or "head.json" in str(raised.value) or "hypotheses" in str(raised.value) or "passes" in str(raised.value) or "residual.json" in str(raised.value) or "validity.json" in str(raised.value)
        problems = TheoryStore.open(damaged).verify()
        assert problems
        assert all(isinstance(line, str) and line.isascii() and "\n" not in line for line in problems)
    assert seen == {
        "missing",
        "stray",
        "other-id",
        "not-json",
        "bad-hypothesis",
        "unsorted",
        "ancestor",
        "duplicate-pass",
        "foreign-pass",
        "bad-phi",
        "bad-residual",
        "bad-validity",
        "next-id",
        "reordered",
    }
    assert store.load().to_dict() == theory.to_dict()
    assert store.verify() == []


def test_head_is_refused_when_it_does_not_describe_this_store(tmp_path: Path) -> None:
    theory = _populated()
    store = TheoryStore.create(tmp_path / "store")
    store.save(theory)
    changes = {
        "schema": lambda data: {**data, "schema": 2},
        "vocab": lambda data: {**data, "vocab": "0" * 64},
        "missing": lambda data: {key: value for key, value in data.items() if key != "version"},
        "twice": lambda data: {**data, "hypotheses": data["hypotheses"] + data["hypotheses"][:1]},
        "bool-generation": lambda data: {**data, "generation": True},
        "bool-next": lambda data: {**data, "next_id": True},
    }
    for name, change in changes.items():
        root = _copy(store.root, tmp_path / name)
        path = root / "head.json"
        _write(path, change(_read(path)))
        with pytest.raises(StoreError) as raised:
            TheoryStore.open(root).load()
        assert "head.json" in str(raised.value)


def test_logs_append_and_a_reopened_store_continues_the_sequence(tmp_path: Path) -> None:
    theory = _populated()
    store = TheoryStore.create(tmp_path / "store")
    assert store.append_journal({"kind": "note", "text": "a"}) == 1
    assert store.append_journal({"kind": "note", "text": "b"}) == 2
    assert store.last_seq == 2
    assert store.journal() == [
        {"kind": "note", "seq": 1, "text": "a"},
        {"kind": "note", "seq": 2, "text": "b"},
    ]
    assert store.journal(after=1) == [{"kind": "note", "seq": 2, "text": "b"}]
    before = (store.root / "journal.jsonl").read_bytes()
    for bad in ({"text": "no kind"}, {"kind": "x", "seq": 9}, "text", {"kind": 3}):
        with pytest.raises(ValueError):
            store.append_journal(bad)
    assert (store.root / "journal.jsonl").read_bytes() == before
    reopened = TheoryStore.open(store.root)
    assert reopened.append_journal({"kind": "note", "text": "c"}) == 3
    assert len(store.journal()) == 3
    one = _edit(theory)
    later = _edit(theory, decision="rolled_back")
    other = _edit(theory, edit_id="e2")
    for edit in (one, other, later):
        store.append_edit(edit)
    assert store.edit_history() == [one, other, later]
    assert store.edits() == [later, other]
    with pytest.raises(ValueError):
        store.append_edit(one.to_dict())
    store.append_negative({"fingerprint": "abc", "edit_id": "e1"})
    assert store.negatives() == [{"fingerprint": "abc", "edit_id": "e1"}]
    negative_before = (store.root / "negative.jsonl").read_bytes()
    for bad in ({}, {"fingerprint": ""}, {"fingerprint": 3}, "abc"):
        with pytest.raises(ValueError):
            store.append_negative(bad)
    assert (store.root / "negative.jsonl").read_bytes() == negative_before
    broken = _copy(store.root, tmp_path / "cut")
    lines = (store.root / "journal.jsonl").read_text(encoding="utf-8").split("\n")
    (broken / "journal.jsonl").write_text("\n".join(lines[1:]), encoding="utf-8", newline="\n")
    with pytest.raises(StoreError) as raised:
        TheoryStore.open(broken)
    assert "journal.jsonl" in str(raised.value)
    assert store.verify() == []


def test_closing_a_generation_snapshots_that_state_and_leaves_the_live_one(tmp_path: Path) -> None:
    theory = _populated()
    empty = Theory()
    store = TheoryStore.create(tmp_path / "store")
    store.save(theory)
    store.append_journal({"kind": "note"})
    live_before = {
        name: blob
        for name, blob in _files(store.root).items()
        if name != "head.json" and not name.startswith("generations/")
    }
    head_before = store.head()
    assert store.close_generation(empty, cause="edit:e1") == 0
    assert store.head()["generation"] == 1
    assert {key: value for key, value in store.head().items() if key != "generation"} == {
        key: value for key, value in head_before.items() if key != "generation"
    }
    assert store.load().to_dict() == theory.to_dict()
    assert {
        name: blob
        for name, blob in _files(store.root).items()
        if name != "head.json" and not name.startswith("generations/")
    } == live_before
    assert store.load_generation(0).to_dict() == empty.to_dict()
    store.append_journal({"kind": "note"})
    store.append_journal({"kind": "note"})
    assert store.close_generation(theory, cause="checkpoint:batch-1") == 1
    assert store.head()["generation"] == 2
    assert store.head()["version"] == theory.version
    assert store.generations() == [
        {"cause": "edit:e1", "generation": 0, "journal_seq": 1, "version": empty.version},
        {"cause": "checkpoint:batch-1", "generation": 1, "journal_seq": 3, "version": theory.version},
    ]
    assert sorted(path.name for path in (store.root / "generations").iterdir()) == [
        "g000000.json",
        "g000001.json",
    ]
    restored = store.load_generation(1)
    assert restored.to_dict() == theory.to_dict()
    assert restored.predict(phi(X3), ORACLE).to_dict() == theory.predict(phi(X3), ORACLE).to_dict()
    with pytest.raises(StoreError):
        store.load_generation(2)
    for bad in (-1, True, "1", 1.0):
        with pytest.raises(ValueError):
            store.load_generation(bad)
    for bad in ("", None, 3):
        with pytest.raises(ValueError):
            store.close_generation(theory, cause=bad)
    assert store.verify() == []
    assert TheoryStore.open(store.root).generations() == store.generations()
    # saving afterwards keeps the generation the close advanced
    store.save(theory)
    assert store.head()["generation"] == 2
    assert store.load().to_dict() == theory.to_dict()
    snapshot = (store.root / "generations" / "g000001.json").read_bytes()
    data = _read(store.root / "generations" / "g000001.json")
    assert isinstance(data, dict)
    data["theory"]["next_id"] += 1
    _write(store.root / "generations" / "g000001.json", data)
    with pytest.raises(StoreError) as raised:
        store.load_generation(1)
    assert "generation" in str(raised.value)
    problems = store.verify()
    assert any("generation" in line for line in problems)
    assert all(line.isascii() for line in problems)
    (store.root / "generations" / "g000001.json").write_bytes(snapshot)
    (store.root / "generations" / "g000000.json").unlink()
    assert store.verify()
    # an existing snapshot is not overwritten, and the live head stays put
    fresh = TheoryStore.create(tmp_path / "once")
    fresh.save(theory)
    assert fresh.close_generation(theory, cause="once") == 0
    held = (fresh.root / "generations" / "g000000.json").read_bytes()
    head = _read(fresh.root / "head.json")
    assert isinstance(head, dict)
    head["generation"] = 0
    _write(fresh.root / "head.json", head)
    with pytest.raises(StoreError):
        fresh.close_generation(empty, cause="again")
    assert (fresh.root / "generations" / "g000000.json").read_bytes() == held
    assert _read(fresh.root / "head.json")["generation"] == 0


def test_store_names_are_exported() -> None:
    import surprise.theory as pkg

    for name in (
        "StoreError",
        "TheoryStore",
        "common_conjunction",
        "hypothesis_length",
        "theory_length",
    ):
        assert name in pkg.__all__
        assert hasattr(pkg, name)
    assert pkg.TheoryStore is TheoryStore
    assert pkg.StoreError is StoreError
