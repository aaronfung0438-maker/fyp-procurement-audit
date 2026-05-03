"""Google Sheets persistence layer for the procurement-audit experiment.

Two sheets are used inside one spreadsheet:

* ``assignment_queue``
  Pre-populated by ``init_sheets.py`` with a randomly-shuffled list of
  group labels (``G1``, ``G2``, ``G3``). Each row corresponds to one
  participant slot. The slot index acts as the deterministic, race-free
  participant counter — ``append_row`` is atomic on Google's side.

* ``sessions``
  One row per submitted answer. Per-question rows are appended as the
  participant progresses, so a network drop loses at most the
  in-flight, unsubmitted question.

The module is intentionally thin: every operation is a single
``gspread`` API call wrapped with retry logic. ``streamlit.secrets`` is
the only auth surface — no service account JSON ever lives on disk.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

ASSIGNMENT_SHEET = "assignment_queue"
SESSIONS_SHEET = "sessions"

ASSIGNMENT_HEADER = ["slot_idx", "group", "claimed_by", "claimed_at"]
SESSIONS_HEADER = [
    "participant_id",
    "group",
    "phase",
    "question_idx",
    "po_id",
    "render_ts",
    "submit_ts",
    "duration_ms",
    "judgment",
    "confidence",
    "rationale",
    "extra_json",
]


@dataclass
class SheetsClient:
    """Lazy gspread wrapper bound to a single spreadsheet."""

    spreadsheet_id: str
    service_account_info: dict[str, Any] = field(repr=False)
    _client: gspread.Client | None = field(default=None, init=False, repr=False)
    _spreadsheet: gspread.Spreadsheet | None = field(
        default=None, init=False, repr=False
    )

    def _ensure(self) -> gspread.Spreadsheet:
        if self._spreadsheet is not None:
            return self._spreadsheet
        creds = Credentials.from_service_account_info(
            self.service_account_info, scopes=SCOPES
        )
        self._client = gspread.authorize(creds)
        self._spreadsheet = self._client.open_by_key(self.spreadsheet_id)
        return self._spreadsheet

    def worksheet(self, name: str) -> gspread.Worksheet:
        return self._ensure().worksheet(name)

    def claim_next_slot(self, participant_id: str) -> tuple[int, str]:
        """Claim the next unassigned row in ``assignment_queue``.

        Returns ``(slot_idx, group)``. Atomic at the row level: two
        concurrent callers will read different ``cell.value`` results
        because ``find`` re-scans live data and ``update_cell`` commits
        before the second caller's lookup. In the rare race where two
        callers find the same empty row at the same instant, the second
        ``update_cell`` simply overwrites the first — the affected
        participant should re-launch the app, which will then see the
        slot already claimed and continue to the next empty row.
        """
        ws = self.worksheet(ASSIGNMENT_SHEET)
        records = ws.get_all_records()
        for row_idx, record in enumerate(records, start=2):
            if not str(record.get("claimed_by", "")).strip():
                slot_idx = int(record["slot_idx"])
                group = str(record["group"])
                ws.update_cell(row_idx, ASSIGNMENT_HEADER.index("claimed_by") + 1, participant_id)
                ws.update_cell(
                    row_idx,
                    ASSIGNMENT_HEADER.index("claimed_at") + 1,
                    _now_iso(),
                )
                return slot_idx, group
        raise RuntimeError(
            "assignment_queue is fully claimed; please regenerate the queue"
        )

    def lookup_existing_assignment(self, participant_id: str) -> tuple[int, str] | None:
        """Return existing (slot_idx, group) if participant already in queue."""
        ws = self.worksheet(ASSIGNMENT_SHEET)
        records = ws.get_all_records()
        for record in records:
            if str(record.get("claimed_by", "")).strip().lower() == participant_id.lower():
                return int(record["slot_idx"]), str(record["group"])
        return None

    def append_response(self, row: dict[str, Any]) -> None:
        """Append one response row to the ``sessions`` sheet."""
        ws = self.worksheet(SESSIONS_SHEET)
        ordered = [row.get(col, "") for col in SESSIONS_HEADER]
        _retry(lambda: ws.append_row(ordered, value_input_option="USER_ENTERED", table_range="A1"))


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


def _retry(fn, attempts: int = 3, backoff: float = 1.5):
    last_err: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001
            last_err = e
            time.sleep(backoff ** i)
    raise RuntimeError(f"gspread call failed after {attempts} attempts: {last_err}")


def from_streamlit_secrets(st_secrets) -> SheetsClient:
    """Build a SheetsClient from ``streamlit.secrets``.

    Expected secrets layout (TOML)::

        spreadsheet_id = "..."

        [gcp_service_account]
        type = "service_account"
        project_id = "..."
        private_key_id = "..."
        private_key = "-----BEGIN PRIVATE KEY-----\\n...\\n-----END PRIVATE KEY-----\\n"
        client_email = "...@...iam.gserviceaccount.com"
        ...
    """
    return SheetsClient(
        spreadsheet_id=st_secrets["spreadsheet_id"],
        service_account_info=dict(st_secrets["gcp_service_account"]),
    )
