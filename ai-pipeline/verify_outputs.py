"""Independent source/artifact/split/metric consistency gate; fail loudly."""
import argparse
import hashlib
import importlib.util
import itertools
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

import pipeline
import serving


def verify(data_root, out):
    summary = pipeline.read_json(out / "summary.json")
    evaluation = pipeline.read_json(out / "evaluation.json")
    for source in summary["source_hashes"]:
        assert pipeline.sha256(data_root / source["path"]) == source["sha256"]
    for artifact in pipeline.read_json(out / "artifact_manifest.json")["artifacts"]:
        assert pipeline.sha256(out / artifact["file"]) == artifact["sha256"], artifact["file"]
    f = pd.read_csv(data_root / "raw/04_uci_shoppers/online_shoppers_intention.csv")
    x, y, groups, splits = pipeline.prepare_splits(f)
    assert "PageValues" not in evaluation["features"] and "Revenue" not in evaluation["features"]
    assert evaluation["features"] == pipeline.FEATURES
    assert len(f) == 12330 and int(y.sum()) == 1908
    assert sum(len(v) for v in splits.values()) == len(f)
    for a, b in itertools.combinations(splits, 2):
        assert not set(groups[splits[a]]) & set(groups[splits[b]])
        assert not set(splits[a]) & set(splits[b])
    for name, indices in splits.items():
        digest = hashlib.sha256(np.asarray(indices, dtype="int64").tobytes()).hexdigest()
        assert digest == evaluation["splits"][name]["indices_sha256"]
    model = joblib.load(out / "intent_model.joblib")
    assert model.n_features_in_ == len(pipeline.FEATURES)
    p = model.predict_proba(x.iloc[splits["test"]])[:, 1]
    actual = pipeline.metrics(y[splits["test"]], p)
    saved = evaluation["models"][evaluation["selected_model"]]["test"]
    for name in ["auroc", "pr_auc_average_precision", "brier", "ece_10bins"]:
        assert abs(actual[name] - saved[name]) < 1e-12, name
    audit = summary["retail"]["audit"]
    assert audit["matched_rows"] == 541909 and audit["d2_only_rows"] == 0
    assert audit["d3_second_sheet_only_rows"] == 1
    assert summary["d1"]["none_categories_preserved"] == {"Social_Media_Influence": 247, "Engagement_with_Ads": 256}
    assert sum(v["customers"] for v in summary["d1"]["categories"]) == 1000
    demand = summary["retail"]["demand_backtest"]
    assert demand["test_months"] == 11
    assert demand["observations"][0]["month"] == "2011-01"
    assert demand["observations"][-1]["month"] == "2011-11"
    for name, values in demand["models"].items():
        error = sum(abs(r["actual_units"] - r[name]) for r in demand["observations"])
        assert abs(values["wape"] - error / sum(r["actual_units"] for r in demand["observations"])) < 1e-12
    rules = pipeline.read_json(out / "bundle_rules.json")
    assert rules
    for r in rules:
        assert r["joint_invoices"] >= 100
        assert abs(r["support"] - r["joint_invoices"] / r["total_invoices"]) < 1e-12
        assert abs(r["confidence"] - r["joint_invoices"] / r["antecedent_invoices"]) < 1e-12
        assert abs(r["lift"] - r["confidence"] / (r["consequent_invoices"] / r["total_invoices"])) < 1e-12
        assert r["source"].startswith("D3") and r["experimental"]
    # Actual dynamic import as the backend will do; no package-name assumptions.
    spec = importlib.util.spec_from_file_location("modu_pipeline_serving", Path(__file__).parent / "serving.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    example = dict(zip(pipeline.FEATURES, [1, 12, 0, 0, 8, 120, 0, 0]))
    score = module.predict_intent(example)
    assert 0 <= score["probability"] <= 1 and score["experimental"]
    invalid = [dict(example, PageValues=99), {k: v for k, v in example.items() if k != "Weekend"},
               dict(example, ProductRelated=-1), dict(example, Weekend=2), dict(example, SpecialDay=1.1),
               dict(example, Administrative_Duration=float("nan")), dict(example, ProductRelated=1.5)]
    for values in invalid:
        try:
            module.predict_intent(values)
        except ValueError:
            continue
        raise AssertionError("Invalid model features accepted")
    assert module.get_summary()["experimental"] and len(module.get_bundle_examples()) == 12
    print("DATA_PIPELINE_PASS")
    print("source_sha256=4 artifacts=all duplicate_feature_overlap=0 selected_test_metrics=reproduced invalid_inputs=7_rejected")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=Path("D:/파이널프로젝트/data"))
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent / "artifacts")
    args = parser.parse_args()
    verify(args.data_root, args.output)
