"""Convert credentials.json + sheet ID into a working secrets.toml.

Avoids the manual-TOML pitfalls around the multi-line private_key field
by emitting it as a single-line string with explicit ``\\n`` escapes
(which TOML and the Python TOML parser both accept cleanly).

Run once::

    python make_secrets.py --spreadsheet-id <SHEET_ID>

Reads ``credentials.json`` from the same folder by default and writes
``.streamlit/secrets.toml``. Refuses to overwrite an existing file
unless ``--force`` is given.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _toml_str(value: str) -> str:
    """Emit a TOML-safe double-quoted single-line string."""
    escaped = value.replace("\\", "\\\\").replace("\n", "\\n").replace('"', '\\"')
    return f'"{escaped}"'


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spreadsheet-id", required=True)
    parser.add_argument("--credentials", default="credentials.json")
    parser.add_argument("--out", default=".streamlit/secrets.toml")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    creds_path = Path(args.credentials)
    if not creds_path.exists():
        raise SystemExit(f"Not found: {creds_path}")

    out_path = Path(args.out)
    if out_path.exists() and not args.force:
        raise SystemExit(
            f"{out_path} already exists. Pass --force to overwrite."
        )

    with creds_path.open("r", encoding="utf-8") as f:
        creds = json.load(f)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = []
    lines.append(f"spreadsheet_id = {_toml_str(args.spreadsheet_id)}")
    lines.append("")
    lines.append("[gcp_service_account]")
    for key in [
        "type",
        "project_id",
        "private_key_id",
        "private_key",
        "client_email",
        "client_id",
        "auth_uri",
        "token_uri",
        "auth_provider_x509_cert_url",
        "client_x509_cert_url",
        "universe_domain",
    ]:
        if key in creds:
            lines.append(f"{key} = {_toml_str(str(creds[key]))}")

    out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Wrote {out_path} ({len(lines)} lines).")


if __name__ == "__main__":
    main()
