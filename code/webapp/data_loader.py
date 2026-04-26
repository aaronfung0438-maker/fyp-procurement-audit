"""Load frozen Stage 3 questions and Stage 4 LLM outputs.

Resolves the latest timestamp under ``code/dataset/data/stage3`` and
``code/dataset/data/stage4`` so the webapp always serves the most recent
frozen artefacts.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
STAGE3_DIR = REPO_ROOT / "code" / "dataset" / "data" / "stage3"
STAGE4_DIR = REPO_ROOT / "code" / "dataset" / "data" / "stage4"

TS_RE = re.compile(r"(\d{8}_\d{6})")


def _latest(paths: list[Path]) -> Path:
    """Return the most recent path keyed by embedded YYYYMMDD_HHMMSS."""
    if not paths:
        raise FileNotFoundError("No matching files found")

    def _key(p: Path) -> str:
        m = TS_RE.search(p.name)
        return m.group(1) if m else ""

    return max(paths, key=_key)


@dataclass
class FrozenBundle:
    """Holds all frozen artefacts for a single experiment run."""

    timestamp: str
    experiment_df: pd.DataFrame
    practice_df: pd.DataFrame
    experiment_key_df: pd.DataFrame
    practice_key_df: pd.DataFrame
    g2_exp: dict[str, dict[str, Any]]
    g3_exp: dict[str, dict[str, Any]]
    g2_practice: dict[str, dict[str, Any]]
    g3_practice: dict[str, dict[str, Any]]


def _read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_frozen_bundle() -> FrozenBundle:
    """Resolve and load the most recent Stage 3 + Stage 4 artefacts."""
    exp_xlsx = _latest(list(STAGE3_DIR.glob("experiment_32qs_*.xlsx")))
    pra_xlsx = _latest(list(STAGE3_DIR.glob("practice_2qs_*.xlsx")))
    exp_key = _latest(list(STAGE3_DIR.glob("experiment_32qs_*_KEY.xlsx")))
    pra_key = _latest(list(STAGE3_DIR.glob("practice_2qs_*_KEY.xlsx")))

    g2_exp_path = _latest(list(STAGE4_DIR.glob("g2_verdicts_exp_*.json")))
    g3_exp_path = _latest(list(STAGE4_DIR.glob("g3_evidence_exp_*.json")))
    g2_pra_path = _latest(list(STAGE4_DIR.glob("g2_verdicts_practice_*.json")))
    g3_pra_path = _latest(list(STAGE4_DIR.glob("g3_evidence_practice_*.json")))

    ts_match = TS_RE.search(g3_exp_path.name)
    timestamp = ts_match.group(1) if ts_match else "unknown"

    return FrozenBundle(
        timestamp=timestamp,
        experiment_df=pd.read_excel(exp_xlsx),
        practice_df=pd.read_excel(pra_xlsx),
        experiment_key_df=pd.read_excel(exp_key),
        practice_key_df=pd.read_excel(pra_key),
        g2_exp=_read_json(g2_exp_path),
        g3_exp=_read_json(g3_exp_path),
        g2_practice=_read_json(g2_pra_path),
        g3_practice=_read_json(g3_pra_path),
    )


def truth_lookup(key_df: pd.DataFrame) -> dict[str, str]:
    """Build ``{po_id: 'normal' | 'anomaly'}`` from a KEY dataframe.

    Stage 3's prepare_stage3.py emits ``injection_plan`` with the value
    ``"none"`` for normal orders and one of the 8 anomaly class names
    otherwise; that is the canonical truth column. Earlier-named
    columns (``truth_label`` / ``ground_truth`` / ``is_injected``) are
    accepted as fallbacks for backwards compatibility.
    """
    if "injection_plan" in key_df.columns:
        return {
            po: ("normal" if str(plan).strip().lower() == "none" else "anomaly")
            for po, plan in zip(key_df["po_id"], key_df["injection_plan"])
        }
    if "truth_label" in key_df.columns:
        return dict(zip(key_df["po_id"], key_df["truth_label"].str.lower()))
    if "ground_truth" in key_df.columns:
        return dict(zip(key_df["po_id"], key_df["ground_truth"].str.lower()))
    if "is_injected" in key_df.columns:
        return {
            po: ("anomaly" if bool(flag) else "normal")
            for po, flag in zip(key_df["po_id"], key_df["is_injected"])
        }
    raise KeyError(
        "KEY dataframe is missing expected columns: "
        "injection_plan / truth_label / ground_truth / is_injected"
    )


def class_lookup(key_df: pd.DataFrame) -> dict[str, str]:
    """Return ``{po_id: injection_plan}`` (multi-class label).

    ``injection_plan`` is one of ``{"none", "item_spending", "border_value",
    "unusual_vendor", "vendor_spending", "approval_bypass",
    "quote_manipulation", "bank_account_change", "conflict_of_interest"}``.
    """
    if "injection_plan" not in key_df.columns:
        raise KeyError("KEY dataframe is missing 'injection_plan'")
    return {
        po: str(plan).strip().lower()
        for po, plan in zip(key_df["po_id"], key_df["injection_plan"])
    }


if __name__ == "__main__":
    bundle = load_frozen_bundle()
    print(f"Loaded bundle ts={bundle.timestamp}")
    print(f"  experiment rows: {len(bundle.experiment_df)}")
    print(f"  practice rows:   {len(bundle.practice_df)}")
    print(f"  g2_exp keys:     {len(bundle.g2_exp)}")
    print(f"  g3_exp keys:     {len(bundle.g3_exp)}")
