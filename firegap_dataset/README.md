# FireGap dataset (NASA PSI)
- tests.csv — 1372 тестов (FLEX, BASS, BASS-II, ACME CFI-G / Flame Design / BRE, Saffire I–III)
- test_days.csv — журналы по дням (ACME CLD, E-FIELD, s-Flame, BRE): 88 дней
- studies.json — метаданные исследований и публикации; skipped_rows.json, planned_envelopes.csv (FLEX-2 — только план)
- data/ — файлы, собранные вручную/из PDF (BRE из диссертации, E-FIELD Table 1)
- scripts/rebuild_all.sh — пересборка (нужны исходные загрузки PSI), charts/ — графики
Колонка data_quality_note в каждой строке описывает исправления и сомнения.
