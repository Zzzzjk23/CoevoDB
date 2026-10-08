"""Round-trip, defaults, and validation for the five surprise contracts."""

from __future__ import annotations

import dataclasses
import json

import pytest

from surprise.harness.constants import QUERY_TIMEOUT_S, as_dict
from surprise.harness.contracts import (
    FAIL_KINDS,
    INVALID_REASONS,
    LABELS,
    ORACLE_IDS,
    SCHEMA_VERSION,
    ExperimentRecord,
    IdentityEvidence,
    Label,
    SqlCase,
)
from surprise.theory.contracts import EDIT_DECISIONS, Hypothesis, Spec, TheoryEdit


def _assert_round_trip(obj: object) -> None:
    cls = type(obj)
    data = obj.to_dict()
    json.dumps(data)
    text = json.dumps(data, sort_keys=True)
    assert cls.from_dict(json.loads(text)) == obj
    assert json.loads(obj.to_json()) == data
    assert cls.from_json(obj.to_json()) == obj
    assert cls.from_json(obj.to_json()).to_json() == obj.to_json()
    assert obj.to_json() == json.dumps(
        data, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )


def _case() -> SqlCase:
    return SqlCase(
        engine="duckdb",
        setup=["CREATE TABLE t(a INT, note VARCHAR)", "INSERT INTO t VALUES (1, '中文')"],
        query="SELECT note FROM t",
        predicate="note <> '中文'",
    )


def _label() -> Label:
    return Label(
        y="fail",
        oracle="plan_variant",
        fail_kind="wrong_result",
        identity=IdentityEvidence(
            switches=["no_optimizer"],
            error_class="InternalException",
            behavior={"missing": 1, "extra": ["中文"]},
        ),
        cve={"rerun": {"stable": True}},
        detail={"queries": ["q1", "q2"], "note": "中文"},
    )


def _record() -> ExperimentRecord:
    return ExperimentRecord(
        record_id="exp-9",
        run_id="run-9",
        seq=3,
        case=_case(),
        label=_label(),
        purpose="边界",
        created_at="2026-10-08T08:30:00+00:00",
        spec={"engine": "duckdb", "oracle": "tlp", "required": ["exists"]},
        phi={"ast": ["SELECT", "中文"]},
        theory_version="T3",
        p_t=0.25,
        surprise=2.0,
    )


def _spec() -> Spec:
    return Spec(
        engine="datafusion",
        oracle="norec",
        required=["correlated_exists"],
        forbidden=["limit"],
        data_properties=["left_has_dups"],
    )


def _hypothesis() -> Hypothesis:
    return Hypothesis(
        hypothesis_id="h-east",
        engine="duckdb",
        interventions=["deliminator", "filter_pushdown"],
        plan_delta=["HASH_JOIN"],
        versions={"1.1.3": "fail", "1.5.5": "fail"},
        specific=["correlated_exists", "neq"],
        general=[["correlated_exists"], ["neq", "join"]],
        positives=["exp-9"],
        negatives=["exp-1", "exp-2"],
        source="deterministic",
        status="proposed",
    )


def _edit() -> TheoryEdit:
    return TheoryEdit(
        edit_id="e-east",
        kind="new_hypothesis",
        rationale="留入下降",
        bets=[{"spec": _spec().to_dict(), "predicted": "fail"}],
        surprise_delta_in=-1.5,
        surprise_delta_out=0.0,
        decision="accepted",
        proposer="deterministic",
        theory_version="T4",
        payload={"hypothesis": "h-east"},
    )


def test_registries_match_the_plan():
    assert SCHEMA_VERSION == 1
    assert LABELS == ("pass", "fail", "invalid")
    assert ORACLE_IDS == (
        "tlp",
        "norec",
        "plan_variant",
        "index_presence",
        "equivalent_query",
        "version_differential",
        "cross_dbms",
    )
    assert FAIL_KINDS == ("wrong_result", "error_mismatch", "crash")
    assert INVALID_REASONS == (
        "setup_error",
        "nondeterministic",
        "not_applicable",
        "query_error",
        "value_dependent_error",
        "timeout",
        "harness_error",
        "untrusted_rewrite",
        "direction_unknown",
        "insufficient_engines",
        "non_unique_outlier",
        "unstable_rerun",
        "unspecified_semantics",
        "side_effecting_statement",
        "incomparable_results",
        "unattributed_crash",
        "not_reproduced_minimized",
    )
    assert EDIT_DECISIONS == ("pending", "accepted", "rolled_back")


def test_constants_collect_public_uppercase_names():
    snapshot = as_dict()
    assert snapshot["QUERY_TIMEOUT_S"] == 10.0
    assert snapshot["QUERY_TIMEOUT_S"] == QUERY_TIMEOUT_S
    assert set(snapshot) == {
        "CVE_RERUN_ATTEMPTS",
        "CVE_RERUN_EXTENDED",
        "CVE_WALL_TIMEOUT_S",
        "QUERY_TIMEOUT_S",
    }
    assert snapshot["CVE_RERUN_ATTEMPTS"] == 5
    assert snapshot["CVE_RERUN_EXTENDED"] == 15
    assert snapshot["CVE_WALL_TIMEOUT_S"] == 120.0
    json.dumps(snapshot)
    snapshot["QUERY_TIMEOUT_S"] = 0
    assert QUERY_TIMEOUT_S == 10.0
    assert as_dict()["QUERY_TIMEOUT_S"] == 10.0


def test_every_contract_round_trips_through_json():
    objects = [
        _case(),
        IdentityEvidence(),
        IdentityEvidence(switches=["no_optimizer"], behavior={"missing": 2}),
        Label(y="pass", oracle="tlp"),
        Label(y="invalid", oracle="norec", invalid_reason="timeout"),
        _label(),
        _record(),
        ExperimentRecord(
            record_id="exp-bare",
            run_id="run-9",
            seq=1,
            case=_case(),
            label=Label(y="pass", oracle="equivalent_query"),
            purpose="baseline",
            created_at="2026-10-08T08:30:01+00:00",
        ),
        _spec(),
        Spec(engine="duckdb", oracle="cross_dbms"),
        _hypothesis(),
        _edit(),
        TheoryEdit(
            edit_id="e-open",
            kind="note",
            rationale="等待",
            bets=[],
            surprise_delta_in=None,
            surprise_delta_out=None,
            decision="pending",
            proposer="human",
        ),
    ]
    for obj in objects:
        _assert_round_trip(obj)


def test_to_json_keeps_non_ascii_characters():
    text = _case().to_json()
    assert "中文" in text
    assert "\\u" not in text


def test_lists_become_tuples_including_nested_ones():
    setup = ["CREATE TABLE t(a INT)", "INSERT INTO t VALUES (1)"]
    case = SqlCase(engine="duckdb", setup=setup, query="SELECT a FROM t")
    assert case.setup == ("CREATE TABLE t(a INT)", "INSERT INTO t VALUES (1)")
    assert setup == ["CREATE TABLE t(a INT)", "INSERT INTO t VALUES (1)"]

    general = [["correlated_exists"], ["neq"]]
    hypothesis = Hypothesis(
        hypothesis_id="h",
        engine="duckdb",
        interventions=["deliminator"],
        plan_delta=[],
        versions={},
        specific=["neq"],
        general=general,
        positives=[],
        negatives=[],
        source="deterministic",
        status="proposed",
    )
    assert hypothesis.interventions == ("deliminator",)
    assert hypothesis.plan_delta == ()
    assert hypothesis.general == (("correlated_exists",), ("neq",))
    assert hypothesis.positives == ()
    assert general == [["correlated_exists"], ["neq"]]

    bets = [{"predicted": "fail"}]
    edit = TheoryEdit(
        edit_id="e",
        kind="k",
        rationale="r",
        bets=bets,
        surprise_delta_in=None,
        surprise_delta_out=None,
        decision="rolled_back",
        proposer="p",
    )
    assert edit.bets == ({"predicted": "fail"},)
    bets[0]["predicted"] = "pass"
    assert edit.bets == ({"predicted": "fail"},)


def test_defaults_and_dict_isolation():
    case = SqlCase(engine="duckdb", setup=(), query="SELECT 1")
    assert case.predicate is None

    behavior = {"missing": 1}
    evidence = IdentityEvidence(behavior=behavior)
    behavior["extra"] = 9
    assert evidence.switches == ()
    assert evidence.error_class is None
    assert evidence.behavior == {"missing": 1}
    assert evidence == IdentityEvidence(behavior={"missing": 1})

    detail = {"form": "where"}
    label = Label(y="pass", oracle="tlp", detail=detail)
    detail["form"] = "mutated"
    assert label.fail_kind is None
    assert label.invalid_reason is None
    assert label.identity == IdentityEvidence()
    assert label.cve == {}
    assert label.detail == {"form": "where"}

    bare = ExperimentRecord(
        record_id="id",
        run_id="run",
        seq=1,
        case=case,
        label=label,
        purpose="check",
        created_at="2026-10-08T00:00:00+00:00",
    )
    assert (bare.spec, bare.phi, bare.theory_version, bare.p_t, bare.surprise) == (
        None,
        None,
        None,
        None,
        None,
    )

    spec = Spec(engine="duckdb", oracle="index_presence")
    assert (spec.required, spec.forbidden, spec.data_properties) == ((), (), ())

    edit = TheoryEdit(
        edit_id="e",
        kind="k",
        rationale="r",
        bets=(),
        surprise_delta_in=None,
        surprise_delta_out=None,
        decision="pending",
        proposer="p",
    )
    assert edit.theory_version is None
    assert edit.payload == {}

    with pytest.raises(dataclasses.FrozenInstanceError):
        case.query = "SELECT 2"  # type: ignore[misc]


def test_tuple_inside_a_dict_is_stored_as_a_list():
    evidence = IdentityEvidence(behavior={"switches": ("no_optimizer",)})
    assert evidence.behavior == {"switches": ["no_optimizer"]}
    _assert_round_trip(evidence)


def test_from_dict_fills_missing_optional_keys():
    case = SqlCase.from_dict(
        {"engine": "duckdb", "setup": ["CREATE TABLE t(a INT)"], "query": "SELECT 1"}
    )
    assert case.predicate is None
    assert case.setup == ("CREATE TABLE t(a INT)",)

    label = Label.from_dict({"y": "pass", "oracle": "version_differential"})
    assert label.identity == IdentityEvidence()
    assert label.cve == {}
    assert label.detail == {}
    assert label.fail_kind is None

    record = ExperimentRecord.from_dict(
        {
            "record_id": "id",
            "run_id": "run",
            "seq": 1,
            "case": case.to_dict(),
            "label": label.to_dict(),
            "purpose": "check",
            "created_at": "2026-10-08T00:00:00Z",
        }
    )
    assert record.spec is None
    assert record.p_t is None
    assert record.surprise is None

    spec = Spec.from_dict({"engine": "duckdb", "oracle": "tlp"})
    assert spec.required == ()

    edit = TheoryEdit.from_dict(
        {
            "edit_id": "e",
            "kind": "k",
            "rationale": "r",
            "bets": [],
            "surprise_delta_in": None,
            "surprise_delta_out": None,
            "decision": "pending",
            "proposer": "p",
        }
    )
    assert edit.payload == {}
    assert edit.theory_version is None


def test_from_dict_rejects_missing_required_keys_and_unknown_keys():
    with pytest.raises(ValueError) as missing:
        SqlCase.from_dict({"engine": "duckdb", "setup": []})
    assert "query" in str(missing.value)

    with pytest.raises(ValueError) as unknown:
        Label.from_dict({"y": "pass", "oracle": "tlp", "extra": 1})
    assert "extra" in str(unknown.value)

    with pytest.raises(ValueError) as nested:
        ExperimentRecord.from_dict(
            {
                "record_id": "id",
                "run_id": "run",
                "seq": 1,
                "case": {"engine": "duckdb", "query": "SELECT 1"},
                "label": {"y": "pass", "oracle": "tlp"},
                "purpose": "check",
                "created_at": "2026-10-08T00:00:00+00:00",
            }
        )
    assert "setup" in str(nested.value)

    with pytest.raises(ValueError) as edit_key:
        TheoryEdit.from_dict(
            {
                "edit_id": "e",
                "kind": "k",
                "rationale": "r",
                "bets": [],
                "surprise_delta_in": None,
                "surprise_delta_out": None,
                "decision": "pending",
                "proposer": "p",
                "note": "nope",
            }
        )
    assert "note" in str(edit_key.value)

    with pytest.raises(ValueError) as not_object:
        Hypothesis.from_dict(["not", "an", "object"])
    assert "Hypothesis" in str(not_object.value)

    with pytest.raises(ValueError) as bad_json:
        Spec.from_json("{")
    assert "Spec" in str(bad_json.value)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"y": "maybe", "oracle": "tlp"},
        {"y": "pass", "oracle": "no_such_oracle"},
        {"y": "fail", "oracle": "tlp"},
        {"y": "fail", "oracle": "tlp", "fail_kind": "bogus"},
        {"y": "invalid", "oracle": "tlp"},
        {"y": "invalid", "oracle": "tlp", "invalid_reason": "bogus"},
        {"y": "pass", "oracle": "tlp", "fail_kind": "crash"},
        {"y": "pass", "oracle": "tlp", "invalid_reason": "timeout"},
        {"y": "fail", "oracle": "tlp", "fail_kind": "crash", "invalid_reason": "timeout"},
        {"y": "invalid", "oracle": "tlp", "invalid_reason": "timeout", "fail_kind": "crash"},
    ],
)
def test_label_rules(kwargs):
    with pytest.raises(ValueError) as caught:
        Label(**kwargs)
    message = str(caught.value)
    assert "y" in message or "oracle" in message or "fail_kind" in message or "invalid_reason" in message


@pytest.mark.parametrize("kind", FAIL_KINDS)
def test_each_fail_kind_is_accepted(kind):
    label = Label(y="fail", oracle="tlp", fail_kind=kind)
    assert label.invalid_reason is None
    _assert_round_trip(label)


@pytest.mark.parametrize("reason", INVALID_REASONS)
def test_each_invalid_reason_is_accepted(reason):
    label = Label(y="invalid", oracle="cross_dbms", invalid_reason=reason)
    assert label.fail_kind is None
    _assert_round_trip(label)


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("engine", ""),
        ("engine", None),
        ("query", ""),
        ("setup", "CREATE TABLE t(a INT)"),
        ("setup", ["CREATE TABLE t(a INT)", 1]),
        ("predicate", 1),
    ],
)
def test_sql_case_rejects_bad_fields(field_name, value):
    kwargs = {"engine": "duckdb", "setup": (), "query": "SELECT 1", field_name: value}
    with pytest.raises(ValueError) as caught:
        SqlCase(**kwargs)
    assert field_name in str(caught.value)


@pytest.mark.parametrize(
    "overrides",
    [
        {"record_id": ""},
        {"run_id": ""},
        {"purpose": ""},
        {"seq": 0},
        {"seq": -3},
        {"seq": True},
        {"seq": 1.5},
        {"created_at": ""},
        {"created_at": "yesterday"},
        {"p_t": -0.01},
        {"p_t": 1.01},
        {"p_t": True},
        {"surprise": "high"},
        {"spec": ["not", "an", "object"]},
        {"case": {"engine": "duckdb"}},
        {"label": "pass"},
    ],
)
def test_experiment_record_rules(overrides):
    case = SqlCase(engine="duckdb", setup=(), query="SELECT 1")
    label = Label(y="pass", oracle="tlp")
    kwargs = {
        "record_id": "id",
        "run_id": "run",
        "seq": 1,
        "case": case,
        "label": label,
        "purpose": "check",
        "created_at": "2026-10-08T00:00:00+00:00",
    }
    kwargs.update(overrides)
    with pytest.raises(ValueError) as caught:
        ExperimentRecord(**kwargs)
    assert str(caught.value)


def test_experiment_record_accepts_probability_endpoints():
    case = SqlCase(engine="duckdb", setup=(), query="SELECT 1")
    label = Label(y="pass", oracle="tlp")
    for probability in (0, 1, 0.0, 1.0):
        record = ExperimentRecord(
            record_id="id",
            run_id="run",
            seq=1,
            case=case,
            label=label,
            purpose="check",
            created_at="2026-10-08T00:00:00+00:00",
            p_t=probability,
            surprise=-0.5,
        )
        assert record.p_t == probability
        _assert_round_trip(record)


def test_spec_and_theory_edit_choices():
    with pytest.raises(ValueError) as bad_oracle:
        Spec(engine="duckdb", oracle="no_such_oracle")
    assert "oracle" in str(bad_oracle.value)
    assert "no_such_oracle" in str(bad_oracle.value)

    with pytest.raises(ValueError) as bad_decision:
        TheoryEdit(
            edit_id="e",
            kind="k",
            rationale="r",
            bets=[],
            surprise_delta_in=None,
            surprise_delta_out=None,
            decision="maybe",
            proposer="p",
        )
    assert "decision" in str(bad_decision.value)
    assert "maybe" in str(bad_decision.value)

    with pytest.raises(ValueError) as bad_general:
        Hypothesis(
            hypothesis_id="h",
            engine="duckdb",
            interventions=(),
            plan_delta=(),
            versions={},
            specific=(),
            general="correlated_exists",
            positives=(),
            negatives=(),
            source="s",
            status="open",
        )
    assert "general" in str(bad_general.value)

    for decision in EDIT_DECISIONS:
        edit = TheoryEdit(
            edit_id="e",
            kind="k",
            rationale="r",
            bets=(),
            surprise_delta_in=None,
            surprise_delta_out=None,
            decision=decision,
            proposer="p",
        )
        assert edit.decision == decision
        _assert_round_trip(edit)


def test_explicit_null_is_not_a_missing_optional_key():
    with pytest.raises(ValueError) as caught:
        Label.from_dict({"y": "pass", "oracle": "tlp", "cve": None})
    assert "cve" in str(caught.value)

    record = ExperimentRecord.from_dict(
        {
            "record_id": "id",
            "run_id": "run",
            "seq": 1,
            "case": {"engine": "duckdb", "setup": [], "query": "SELECT 1"},
            "label": {"y": "pass", "oracle": "tlp"},
            "purpose": "check",
            "created_at": "2026-10-08T00:00:00+00:00",
            "p_t": None,
            "spec": None,
        }
    )
    assert record.p_t is None
    assert record.spec is None
