"""Da eseguire una volta per verificare la struttura reale della board
Timesheet (mai verificata, vedi CLAUDE.md §2) e confrontarla con le colonne
che l'app si aspetta di trovare (config.TIMESHEET_EXPECTED_COLUMNS).

Uso: python scripts/inspect_timesheet_schema.py
Richiede MONDAY_API_TOKEN in .env. Sola lettura, nessuna scrittura.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
import monday_client as mc

if __name__ == "__main__":
    columns = mc.get_board_columns(config.BOARD_TIMESHEET)
    print(f"Board Timesheet ({config.BOARD_TIMESHEET}) — {len(columns)} colonne:")
    for col_id, col in columns.items():
        print(f"  {col_id:30s} {col['type']:20s} {col['title']}")

    print("\nMapping risolto dall'app (per titolo):")
    resolved = mc.resolve_timesheet_columns()
    for key, col_id in resolved.items():
        status = col_id if col_id else "NON TROVATA"
        print(f"  {key:12s} -> {status}")
