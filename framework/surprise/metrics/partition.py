"""Pair agreement of two family partitions, including the adjusted Rand index."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def _choose2(count: int) -> int:
    return count * (count - 1) // 2


def pair_agreement(pred: Mapping[Any, Any], truth: Mapping[Any, Any]) -> dict[str, Any]:
    """Agreement on the unordered pairs of items that appear in both mappings.

    A ``None`` value in ``pred`` is its own class, so those items are singletons.
    ``precision``, ``recall``, ``f1`` and ``ari`` are ``None`` when their
    denominator is zero.
    """
    items = [key for key in pred if key in truth]
    pred_class: dict[Any, tuple[Any, ...]] = {}
    singles = 0
    for key in items:
        value = pred[key]
        if value is None:
            pred_class[key] = ("none", singles)
            singles += 1
        else:
            pred_class[key] = ("value", value)
    truth_class = {key: truth[key] for key in items}

    contingency: dict[tuple[Any, Any], int] = {}
    pred_size: dict[Any, int] = {}
    truth_size: dict[Any, int] = {}
    for key in items:
        left = pred_class[key]
        right = truth_class[key]
        contingency[(left, right)] = contingency.get((left, right), 0) + 1
        pred_size[left] = pred_size.get(left, 0) + 1
        truth_size[right] = truth_size.get(right, 0) + 1

    tp = sum(_choose2(count) for count in contingency.values())
    same_pred = sum(_choose2(count) for count in pred_size.values())
    same_truth = sum(_choose2(count) for count in truth_size.values())
    fp = same_pred - tp
    fn = same_truth - tp
    pairs = _choose2(len(items))
    tn = pairs - tp - fp - fn
    precision = None if tp + fp == 0 else tp / (tp + fp)
    recall = None if tp + fn == 0 else tp / (tp + fn)
    if precision is None or recall is None or precision + recall == 0:
        f1 = None
    else:
        f1 = 2 * precision * recall / (precision + recall)
    if pairs == 0:
        ari = None
    else:
        expected = (same_pred * same_truth) / pairs
        maximum = 0.5 * (same_pred + same_truth)
        denominator = maximum - expected
        ari = None if denominator == 0 else (tp - expected) / denominator
    return {
        "items": len(items),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "ari": ari,
    }
