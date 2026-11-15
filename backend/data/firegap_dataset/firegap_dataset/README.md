# FireGap dataset (NASA PSI)
- assistant/firegap_assistant.html — рабочий прототип: открыть в браузере, ввести O₂ и давление. Ответ строится только по тестам из датасета, без генерации текста моделью (шаблоны в assistant/engine.js). Сборка: scripts/build_assistant.py
- tests.csv — 1372 теста (FLEX, BASS, BASS-II, ACME CFI-G / Flame Design / BRE, Saffire I–III)
- test_days.csv — журналы по дням (ACME CLD, E-FIELD, s-Flame, BRE): 88 дней
- studies.json — метаданные исследований и публикации; skipped_rows.json, planned_envelopes.csv (FLEX-2 — только план)
- data/ — файлы, собранные вручную/из PDF (BRE из диссертации, E-FIELD Table 1)
- scripts/rebuild_all.sh — пересборка датасета (нужны исходные загрузки PSI), charts/ — графики
Колонка data_quality_note в каждой строке описывает исправления и сомнения.

## external_sources.csv (data/)
Внешние источники вне PSI: NASA-STD-6001 (прочитан целиком, с номерами страниц) и литература по частичной гравитации, атмосферам для Луны/Марса, ESA/JAXA/ZARM.
Колонка `verified`: «полный текст» — файл прочитан; «аннотация/выдержка» — виден только фрагмент, числа из таблиц не извлекались. Не смешивать с данными PSI в расчётах: в ассистенте использовать с `source_type` ≠ PSI.

## facts_all.csv (data/)
Единая таблица фактов: G01–G20 (руководство по МКС, стр. указаны) + X01–X31 (NASA-STD-6001 и литература). Колонки `source_type`, `where`, `verified` общие. Это справочные факты с источниками, а не строки экспериментов: в `tests.csv` их смешивать нельзя (там условия O₂ × давление для карты пробелов).
