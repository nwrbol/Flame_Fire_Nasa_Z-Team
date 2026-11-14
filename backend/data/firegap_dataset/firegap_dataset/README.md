# FireGap dataset (NASA PSI)

- `tests.csv`: 1,372 experiment records (FLEX, BASS, BASS-II, ACME CFI-G / Flame Design / BRE, Saffire I-III).
- `test_days.csv`: 88 day-level logs (ACME CLD, E-FIELD, s-Flame, BRE); these are not individual experiment measurements.
- `studies.json`: study metadata and publications supplied by the analysts.
- `skipped_rows.json`: excluded source rows and reasons.
- `planned_envelopes.csv`: FLEX-2 planned ranges, NOT measured results.
- `data/`: manually assembled / PDF-extracted supporting tables.
- `scripts/`: analyst reconstruction scripts, requiring original PSI exports and additional tools. The API does not execute them.
- `charts/`: analyst-generated visualizations; the API does not regenerate them.

Read `data_quality_note` on every record. Preserve raw values, assumptions and missing cells. Some source units, dimensions and metadata are uncertain; this package is not independently validated by the backend.

The backend serves only `tests.csv` by default. Supporting tables and plans are kept separate to avoid double-counting and presenting planned conditions as measured results.
