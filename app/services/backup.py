"""Full-data backup as a ZIP of CSV files (one per table). Password hashes are never included."""
import csv
import io
import json
import zipfile
from datetime import date, datetime, timezone

from sqlalchemy import select

from ..extensions import db

EXCLUDED_COLUMNS = {"password_hash", "code_hash"}


def _cell(value):
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def rows_to_csv(columns, rows):
    """columns: list of names. rows: list of dicts. Returns CSV text, skipping sensitive columns."""
    keep = [c for c in columns if c not in EXCLUDED_COLUMNS]
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(keep)
    for row in rows:
        writer.writerow([_cell(row.get(c)) for c in keep])
    return out.getvalue()


def zip_tables(tables, readme):
    """tables: {name: (columns, rows)}. Returns ZIP bytes."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("README.txt", readme)
        for name, (columns, rows) in tables.items():
            archive.writestr(f"{name}.csv", rows_to_csv(columns, rows))
    return buffer.getvalue()


def build_backup_zip():
    stamp = datetime.now(timezone.utc)
    tables = {}
    for table in db.metadata.sorted_tables:
        result = db.session.execute(select(table))
        tables[table.name] = ([c.name for c in table.columns], [dict(r) for r in result.mappings()])
    readme = (f"VerifyTalent Global data export, created {stamp:%Y-%m-%d %H:%M} UTC.\n"
              "One CSV file per table. Password hashes and verification code hashes are left out.\n"
              "This file contains personal data. Store it somewhere private.\n")
    return zip_tables(tables, readme), f"verifytalent-backup-{stamp:%Y%m%d-%H%M}.zip"
