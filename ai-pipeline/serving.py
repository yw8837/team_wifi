"""Read-only local inference. Load only pipeline-created trusted local artifacts."""
from functools import lru_cache
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ARTIFACTS = HERE / "artifacts"


def _json(name):
    return json.loads((ARTIFACTS / name).read_text(encoding="utf-8"))


def get_summary():
    """Aggregate public-source evidence, no raw customer/person rows."""
    return _json("summary.json")


def get_bundle_examples():
    """Top 12 historical raw-name rules. Never relabel them as childcare goods."""
    return _json("bundle_rules.json")[:12]


@lru_cache(maxsize=1)
def _load_model():
    import joblib
    metadata = _json("model_metadata.json")
    path = ARTIFACTS / "intent_model.joblib"
    if hashlib.sha256(path.read_bytes()).hexdigest() != metadata["model_sha256"]:
        raise RuntimeError("Local model integrity check failed")
    return joblib.load(path), metadata


def predict_intent(features):
    """Predict the UCI end-session target; rejects unsupported/live-claim inputs."""
    import pandas as pd
    metadata = _json("model_metadata.json")
    expected = metadata["features"]
    if not isinstance(features, dict) or set(features) != set(expected):
        raise ValueError("Required features exactly: " + ", ".join(expected))
    clean = {}
    for key in expected:
        value = features[key]
        if isinstance(value, (str, list, dict)) or value is None:
            raise ValueError(f"{key}: finite numeric input required")
        try:
            value = float(value)
        except (TypeError, ValueError, OverflowError):
            raise ValueError(f"{key}: finite numeric input required") from None
        if not math.isfinite(value) or value < 0:
            raise ValueError(f"{key}: finite nonnegative value required")
        if key == "Weekend" and value not in (0, 1):
            raise ValueError("Weekend: 0 or 1 required")
        if key == "SpecialDay" and value > 1:
            raise ValueError("SpecialDay: between 0 and 1 required")
        if key in {"Administrative", "Informational", "ProductRelated"} and not value.is_integer():
            raise ValueError(f"{key}: integer page count required")
        clean[key] = value
    model, metadata = _load_model()
    probability = float(model.predict_proba(pd.DataFrame([clean], columns=expected))[0, 1])
    return {"probability": probability, "model": metadata["selected_model"], "experimental": True,
            "target": "UCI Revenue=True (historical end-session purchase occurrence)",
            "feature_timing": "end-session aggregates; live-prefix validity unverified",
            "limitations": metadata["limitations"], "source_url": "https://archive.ics.uci.edu/dataset/468/online+shoppers+purchasing+intention+dataset"}
