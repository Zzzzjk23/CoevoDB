"""Offline PostgreSQL role evidence and pinned legacy-output regressions."""

from __future__ import annotations

import dataclasses
import hashlib
import json
from types import SimpleNamespace

import pytest

from diagnosis.bisect import POSTGRES_GUC_INTERVENTIONS
from surprise.roles import source
from surprise.roles.conjecturer import select_sources
from surprise.roles.constants import SOURCE_MAX_FILES, SOURCE_MAX_LINES, SOURCE_ROOT_ENV
from surprise.roles.implementer import _DIALECT
from surprise.roles.prior import prior_evidence
from surprise.roles.sources_map import (
    DATAFUSION_SOURCE_RULES,
    EXTRA_SOURCE_COMMITS,
    EXTRA_SOURCE_DIRS,
    POSTGRES_GUC_FILES,
    POSTGRES_SOURCE_RULES,
)


@pytest.fixture(scope="module")
def readers():
    result = source.readers_for(("postgres",))
    assert set(result) == {"duckdb", "datafusion", "postgres"}
    return result


def test_optional_postgres_checkout_is_pinned(readers):
    extra = source.open_extra_sources(("postgres", "postgres"))
    assert set(extra) == {"postgres"}
    assert EXTRA_SOURCE_DIRS == {"postgres": "postgresql-16.15"}
    assert EXTRA_SOURCE_COMMITS == {"postgres": "7d3e000c5961a544302072058a1184e9a588837b"}
    assert extra["postgres"].commit == EXTRA_SOURCE_COMMITS["postgres"]
    assert extra["postgres"].root == readers["postgres"].root


def test_no_optional_engine_needs_no_checkout(monkeypatch):
    def unexpected_lookup():
        pytest.fail("unrequested optional sources must not be looked up")

    monkeypatch.setattr(source, "_default_source_parent", unexpected_lookup)
    assert source.open_extra_sources(()) == {}
    assert source.open_extra_sources(("duckdb", "datafusion")) == {}


def test_missing_optional_checkout_is_reported_once(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv(SOURCE_ROOT_ENV, str(tmp_path))
    assert source.open_extra_sources(("postgres",)) == {}
    stderr = capsys.readouterr().err
    assert len(stderr.splitlines()) == 1
    assert stderr.isascii() and "postgres" in stderr
    assert source.readers_for(("postgres",)) == {}


def test_wrong_commit_is_optional_and_verification_can_be_disabled(monkeypatch, capsys, readers):
    monkeypatch.setitem(EXTRA_SOURCE_COMMITS, "postgres", "0" * 40)
    assert source.open_extra_sources(("postgres",)) == {}
    stderr = capsys.readouterr().err
    assert len(stderr.splitlines()) == 1
    assert stderr.isascii() and "commit mismatch" in stderr
    unchecked = source.open_extra_sources(("postgres",), verify=False)
    assert unchecked["postgres"].root == readers["postgres"].root


def test_readers_keep_legacy_sources_and_only_add_requested_postgres(readers):
    legacy = source.open_sources()
    assert set(legacy) == {"duckdb", "datafusion"}
    duckdb = source.readers_for(("duckdb",))
    assert set(duckdb) == set(legacy)
    for engine, reader in legacy.items():
        assert duckdb[engine].root == readers[engine].root == reader.root
        assert duckdb[engine].commit == readers[engine].commit == reader.commit


def test_legacy_source_failure_does_not_hide_postgres(monkeypatch, readers):
    def unavailable():
        raise source.SourceError("missing legacy checkout")

    monkeypatch.setattr(source, "open_sources", unavailable)
    assert source.readers_for(("duckdb",)) == {}
    assert source.readers_for(("postgres",))["postgres"].root == readers["postgres"].root


def test_postgres_prior_only_reads_release_notes_and_is_repeatable(monkeypatch, readers):
    reader = readers["postgres"]
    original_read = reader.read
    paths = []

    def read(path, *args, **kwargs):
        paths.append(path)
        return original_read(path, *args, **kwargs)

    def no_grep(*args, **kwargs):
        pytest.fail("PostgreSQL prior must not scan adjacent SGML documents")

    monkeypatch.setattr(reader, "read", read)
    monkeypatch.setattr(reader, "grep", no_grep)
    units = ["postgres|plan_variant|join|unknown|unknown", "postgres|tlp|aggregate|unknown|unknown"]
    evidence = prior_evidence(units, readers)
    assert evidence
    assert evidence == prior_evidence(units, readers)
    assert set(paths) == {"doc/src/sgml/release-16.sgml"}
    assert all(line.startswith("EVIDENCE postgres doc/src/sgml/release-16.sgml:") for line in evidence)


def test_postgres_maps_cover_only_available_interventions_and_real_paths(readers):
    unavailable = {"enable_self_join_elimination", "enable_distinct_reordering", "enable_group_by_reordering"}
    assert set(POSTGRES_GUC_FILES) == {name for name, _ in POSTGRES_GUC_INTERVENTIONS} - unavailable
    reader = readers["postgres"]
    for paths in POSTGRES_GUC_FILES.values():
        assert paths
        for path in paths:
            assert reader.exists(path), path
            assert reader.read(path, 1, 1).path == path
    assert [prefix for prefix, _, _ in POSTGRES_SOURCE_RULES] == [prefix for prefix, _, _ in DATAFUSION_SOURCE_RULES]
    for _, regex, under in POSTGRES_SOURCE_RULES:
        assert under.startswith("src/backend/") and reader.exists(under)
        assert reader.grep(regex, under=under, max_hits=1), (regex, under)


def test_postgres_memoize_and_fix_set_budget_follow_table_order(readers):
    memo = select_sources("postgres", SimpleNamespace(interventions=("enable_memoize",)), None, readers)
    assert [s.path for s in memo] == ["src/backend/executor/nodeMemoize.c"]
    assert memo[0].start == 1 and memo[0].end == SOURCE_MAX_LINES
    interventions = ("enable_memoize", "enable_hashjoin")
    result = select_sources("postgres", SimpleNamespace(interventions=interventions), None, readers)
    paths = [*POSTGRES_GUC_FILES["enable_hashjoin"], *POSTGRES_GUC_FILES["enable_memoize"]]
    assert [s.path for s in result] == paths
    assert all(s.start == 1 and s.end == SOURCE_MAX_LINES // len(paths) for s in result)
    assert result == select_sources("postgres", SimpleNamespace(interventions=interventions[::-1]), None, readers)
    capped = select_sources("postgres", SimpleNamespace(interventions=tuple(POSTGRES_GUC_FILES)), None, readers)
    assert len({s.path for s in capped}) == SOURCE_MAX_FILES
    assert sum(s.end - s.start + 1 for s in capped) <= SOURCE_MAX_LINES
    assert select_sources("postgres", SimpleNamespace(interventions=("unknown",)), None, readers) == ()


@pytest.mark.parametrize("prefix,regex,under", POSTGRES_SOURCE_RULES)
def test_each_postgres_feature_rule_selects_source(prefix, regex, under, readers):
    phi = {"features": [prefix + "inner" if prefix.endswith(":") else prefix]}
    result = select_sources("postgres", SimpleNamespace(interventions=()), phi, readers)
    assert result and all(s.path.startswith("src/backend/") for s in result)
    assert result == select_sources("postgres", SimpleNamespace(interventions=()), phi, readers)
    assert len({s.path for s in result}) <= SOURCE_MAX_FILES
    assert sum(s.end - s.start + 1 for s in result) <= SOURCE_MAX_LINES


def test_postgres_dialect_has_runner_constraints():
    hint = _DIALECT["postgres"]
    assert all(word in hint for word in ("PostgreSQL 16", "BEGIN", "COMMIT", "SAVEPOINT", "search_path", "role", "non-superuser"))


def _digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


# Calculated against the pinned checkouts before this work package changed code.
@pytest.mark.parametrize("engine,interventions,features,expected", [
    ("duckdb", ("filter_pushdown", "join_order"), ["ast:join:inner"], "a0a1c5461036adb1bed695ab018940e1201cf6a9cf123c67e9e8b288ad8d4ef8"),
    ("duckdb", (), ["ast:join:inner", "ast:agg"], "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"),
    ("duckdb", (), ["ast:set_op:except", "ast:window_fn:ranking", "ast:clause:order_by"], "4f53cda18c2baa0c0354bb5f9a3ecbe5ed12ab4d8e11ba873c2f11161202b945"),
    ("datafusion", ("filter_pushdown", "join_order"), ["ast:join:inner"], "6d9d4147bc26e6085af095cec720b0f4b0b1d37e12969ea3e2b32b20cdfc127e"),
    ("datafusion", (), ["ast:join:inner", "ast:agg"], "3b136535c80a8c44be199523188b341ba840397f3035e2a80cd00421aadfe7bb"),
    ("datafusion", (), ["ast:set_op:except", "ast:window_fn:ranking", "ast:clause:order_by"], "75a1ebf4cb457cb7fefe525f388c69900d208a4121df3975a7aebffc930da212"),
])
def test_legacy_source_results_match_prechange_snapshot(engine, interventions, features, expected, readers):
    result = select_sources(engine, SimpleNamespace(interventions=interventions), {"features": features}, readers)
    assert _digest([dataclasses.asdict(s) for s in result]) == expected


@pytest.mark.parametrize("engine,constructs,expected", [
    ("duckdb", ("join", "aggregate"), "b2c97e124b2bdaaa04b4df55c8dc927c7ea2ebc1c323ae17a1853d20da2da475"),
    ("duckdb", ("set_op", "window"), "8d67b4736de02a71c963c308e2a65ac200986a73cbcea4cf2931c08e8e38f578"),
    ("datafusion", ("join", "aggregate"), "cdebabe44942c54cc1b6750c8ad6987b9d0d68900f98b3391047baed6a903ea2"),
    ("datafusion", ("set_op", "window"), "28904748ce46120b49f2b53f58036927b204eed54d135e8be13d5b43f04d5dd7"),
])
def test_legacy_prior_results_match_prechange_snapshot(engine, constructs, expected, readers):
    units = [f"{engine}|tlp|{construct}|unknown|unknown" for construct in constructs]
    assert _digest(prior_evidence(units, readers)) == expected
