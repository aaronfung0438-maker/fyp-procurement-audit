"""One-time setup of the Google Sheets backend.

Reads service-account credentials from ``credentials.json`` in the same
directory (kept out of git via .gitignore) and initialises:

* ``assignment_queue`` — pre-populated with N participant slots,
  groups balanced and shuffled with a fixed RNG seed.
* ``sessions``         — empty, headers only.

Run once before any participant uses the app::

    python init_sheets.py --spreadsheet-id <ID> --slots 12 --seed 42

If you need to regenerate the queue (e.g. someone dropped out and you
want to rebalance the remaining slots), pass ``--reset``.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

from sheets_backend import (
    ASSIGNMENT_HEADER,
    ASSIGNMENT_SHEET,
    SCOPES,
    SESSIONS_HEADER,
    SESSIONS_SHEET,
)


def build_balanced_queue(n_slots: int, seed: int) -> list[str]:
    """Return a shuffled list of group labels with as-balanced-as-possible counts.

    For N=12 the result is exactly 4 G1, 4 G2, 4 G3 in random order.
    For N=11 it is 4-4-3 in random order. The shuffling is deterministic
    given ``seed``, so re-running ``init_sheets.py`` with the same
    arguments produces the identical queue.
    """
    groups = ["G1", "G2", "G3"]
    base_count = n_slots // 3
    remainder = n_slots % 3
    pool: list[str] = []
    for i, g in enumerate(groups):
        count = base_count + (1 if i < remainder else 0)
        pool.extend([g] * count)
    rng = random.Random(seed)
    rng.shuffle(pool)
    return pool


def _ensure_worksheet(
    spreadsheet: gspread.Spreadsheet,
    title: str,
    header: list[str],
    *,
    rows: int,
) -> gspread.Worksheet:
    try:
        ws = spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=title, rows=rows, cols=len(header))
    ws.clear()
    ws.update(values=[header], range_name="A1", value_input_option="USER_ENTERED")
    return ws


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spreadsheet-id", required=True)
    parser.add_argument(
        "--credentials",
        default="credentials.json",
        help="Path to local service-account JSON",
    )
    parser.add_argument("--slots", type=int, default=12)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    creds_path = Path(args.credentials)
    if not creds_path.exists():
        raise SystemExit(f"Service-account file not found: {creds_path}")
    with creds_path.open("r", encoding="utf-8") as f:
        info = json.load(f)
    creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    client = gspread.authorize(creds)
    ss = client.open_by_key(args.spreadsheet_id)

    if args.reset:
        for title in (ASSIGNMENT_SHEET, SESSIONS_SHEET):
            try:
                ss.del_worksheet(ss.worksheet(title))
            except gspread.WorksheetNotFound:
                pass

    queue = build_balanced_queue(args.slots, args.seed)
    print(f"Generated queue ({len(queue)}): {queue}")

    aq = _ensure_worksheet(
        ss, ASSIGNMENT_SHEET, ASSIGNMENT_HEADER, rows=args.slots + 5
    )
    rows = [[i + 1, queue[i], "", ""] for i in range(args.slots)]
    aq.update(values=rows, range_name="A2", value_input_option="USER_ENTERED")

    _ensure_worksheet(ss, SESSIONS_SHEET, SESSIONS_HEADER, rows=2000)

    print("Done. Sheets ready.")


if __name__ == "__main__":
    main()
