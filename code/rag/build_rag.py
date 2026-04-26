"""
Stage 4a -- Embed the RAG corpus into a Chroma vector store.

Input:  data/stage3/rag_corpus_*.jsonl
        (produced by prepare_stage3.py; all truth / detector / derived
         columns stripped via make_rag_safe).
        Current pipeline produces 466 documents = 500 - 32 (experiment) - 2 (practice).
Output: data/chroma/                  (ChromaDB persistent store, collection = "po_history")
        data/stage4/build_log_<TS>.json

Usage:
    python build_rag.py
    python build_rag.py --corpus "data/stage3/rag_corpus_466_20260426_040739.jsonl"
    python build_rag.py --reset     # delete existing collection and rebuild from scratch

Dependencies:
    pip install chromadb
    ollama pull nomic-embed-text
"""

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import chromadb
from chromadb.utils import embedding_functions

# ── Constants ─────────────────────────────────────────────────────────────────
EMBED_MODEL     = "nomic-embed-text"
EMBED_URL       = "http://localhost:11434/api/embeddings"
COLLECTION_NAME = "po_history"
BATCH_SIZE      = 50

BASE_DIR   = Path(__file__).parent.parent / "dataset"
STAGE3_DIR = BASE_DIR / "data" / "stage3"
CHROMA_DIR = BASE_DIR / "data" / "chroma"
STAGE4_DIR = BASE_DIR / "data" / "stage4"

# Columns that must NOT appear in the RAG corpus metadata.
# Mirrors TRUTH_COLS + DETECTOR_COLS + DERIVED_COLS in prepare_stage3.py.
# If any are present, the corpus was built without make_rag_safe() and the
# build is aborted to prevent information leakage into the LLM context.
SENSITIVE_COLS = {
    # Ground truth
    "injection_plan", "injection_seed",
    "experiment_stratum", "experiment_block", "target_class", "reason",
    "practice_role",
    # Statistical detectors (linear + log Mahalanobis + rule-based flag)
    "mahalanobis_D2", "mahalanobis_D2_log",
    "D2_percentile",  "D2_log_percentile",
    "risk_tier",      "risk_tier_log",
    "policy_violation",
    # Section E derived features (ratios / z-scores / gaps)
    "expected_unit_price_usd", "unit_price_ratio",
    "expected_quantity",       "quantity_ratio",
    "expected_delivery_lag_mean", "expected_delivery_lag_sigma",
    "delivery_lag_z", "approval_lag_z", "approval_lag_z_log",
    "total_vs_approval_gap",
}


# ── Helpers ───────────────────────────────────────────────────────────────────
def find_latest_corpus(stage3_dir: Path) -> Path:
    candidates = sorted(stage3_dir.glob("rag_corpus_*.jsonl"))
    if not candidates:
        raise FileNotFoundError(
            f"No rag_corpus_*.jsonl found. Run prepare_stage3.py first.\n"
            f"Search path: {stage3_dir}"
        )
    return candidates[-1]


def load_corpus(path: Path) -> list[dict]:
    docs = []
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                doc = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"JSON parse error on line {lineno}: {e}") from e
            for field in ("id", "text", "metadata"):
                if field not in doc:
                    raise ValueError(f"Line {lineno} is missing required field '{field}'")
            docs.append(doc)
    return docs


def check_no_leakage(docs: list[dict]) -> None:
    """Abort if any sensitive column leaked into the metadata."""
    for doc in docs:
        leaked = SENSITIVE_COLS & set(doc.get("metadata", {}).keys())
        if leaked:
            raise ValueError(
                f"Corpus metadata contains sensitive columns {sorted(leaked)}. "
                f"Ensure prepare_stage3.py applied make_rag_safe() before export."
            )


def make_embedding_fn() -> embedding_functions.OllamaEmbeddingFunction:
    return embedding_functions.OllamaEmbeddingFunction(
        url=EMBED_URL,
        model_name=EMBED_MODEL,
    )


# ── Core build ────────────────────────────────────────────────────────────────
def build(corpus_path: Path, reset: bool = False) -> dict:
    print(f"\n=== Stage 4a -- Build RAG ===")
    print(f"Corpus : {corpus_path}")

    docs   = load_corpus(corpus_path)
    n_docs = len(docs)
    print(f"Loaded : {n_docs} documents")

    ids = [d["id"] for d in docs]
    if len(set(ids)) != n_docs:
        raise ValueError("Duplicate ids found in corpus. Check prepare_stage3.py output.")

    check_no_leakage(docs)
    print(f"Leakage check: passed (no sensitive columns in metadata)")

    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    STAGE4_DIR.mkdir(parents=True, exist_ok=True)

    ollama_ef = make_embedding_fn()
    client    = chromadb.PersistentClient(path=str(CHROMA_DIR))

    if reset:
        try:
            client.delete_collection(COLLECTION_NAME)
            print(f"Deleted existing collection '{COLLECTION_NAME}'")
        except Exception:
            pass

    col = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=ollama_ef,
        metadata={"hnsw:space": "cosine"},
    )

    existing = col.count()
    if existing > 0 and not reset:
        print(
            f"Warning: collection already has {existing} documents.\n"
            f"  Running upsert (same ids will be overwritten).\n"
            f"  Use --reset to force a clean rebuild."
        )

    t0 = time.time()
    for i in range(0, n_docs, BATCH_SIZE):
        batch = docs[i : i + BATCH_SIZE]
        col.upsert(
            ids=[d["id"] for d in batch],
            documents=[d["text"] for d in batch],
            metadatas=[d["metadata"] for d in batch],
        )
        done = min(i + BATCH_SIZE, n_docs)
        print(f"  upserted {done:>3}/{n_docs}  ({time.time() - t0:.1f}s)")

    elapsed     = time.time() - t0
    final_count = col.count()
    print(f"\nDone. Collection '{COLLECTION_NAME}' has {final_count} documents.")

    if final_count != n_docs:
        print(
            f"  Warning: final count {final_count} != input count {n_docs}. "
            f"Run with --reset to ensure exact match."
        )

    ts  = datetime.now().strftime("%Y%m%d_%H%M%S")
    log = {
        "built_at":      ts,
        "corpus_path":   str(corpus_path),
        "n_input_docs":  n_docs,
        "n_chroma_docs": final_count,
        "embed_model":   EMBED_MODEL,
        "collection":    COLLECTION_NAME,
        "chroma_dir":    str(CHROMA_DIR),
        "elapsed_sec":   round(elapsed, 1),
        "reset_used":    reset,
    }
    log_path = STAGE4_DIR / f"build_log_{ts}.json"
    log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")
    print(f"Build log saved: {log_path}")
    return log


# ── Smoke test ────────────────────────────────────────────────────────────────
def smoke_test(n_sample: int = 3) -> None:
    """Query n_sample documents against themselves; each should appear in its own top-3."""
    print(f"\n--- Smoke test ({n_sample} queries) ---")
    ollama_ef = make_embedding_fn()
    client    = chromadb.PersistentClient(path=str(CHROMA_DIR))
    col       = client.get_collection(COLLECTION_NAME, embedding_function=ollama_ef)

    sample_ids = col.get(limit=n_sample, include=[])["ids"]
    for qid in sample_ids:
        doc_text = col.get(ids=[qid], include=["documents"])["documents"][0]
        results  = col.query(query_texts=[doc_text], n_results=3, include=[])
        top3     = results["ids"][0]
        print(f"  query={qid}  top3={top3}")
        assert qid in top3, f"Self-retrieval failed: '{qid}' not in top-3 results"
    print("Smoke test passed.")


# ── Entry point ───────────────────────────────────────────────────────────────
def main() -> None:
    parser = argparse.ArgumentParser(description="Stage 4a -- Build Chroma RAG corpus")
    parser.add_argument("--corpus",    type=Path, default=None,
                        help="Path to rag_corpus_*.jsonl (default: auto-detect latest)")
    parser.add_argument("--reset",     action="store_true",
                        help="Delete existing collection before rebuilding")
    parser.add_argument("--no-smoke",  action="store_true",
                        help="Skip smoke test after build")
    args = parser.parse_args()

    corpus_path = args.corpus or find_latest_corpus(STAGE3_DIR)
    build(corpus_path, reset=args.reset)
    if not args.no_smoke:
        smoke_test()
    print("\n=== Stage 4a complete ===\n")


if __name__ == "__main__":
    main()
