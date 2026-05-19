# Lenta CV Price Tag Recognition

MVP для распознавания ценников Ленты по кропам из видеопотока робота, который движется вдоль полки.

Этот репозиторий реализует **OCR/matching backend**: принимает уже подготовленные и сгруппированные кропы ценников, извлекает поля, агрегирует несколько view одного ценника, сопоставляет результат с товарным каталогом и, если доступна reference-БД отдела, безопасно обогащает итоговый CSV.

Детекция, трекинг и нарезка кропов из полного видео могут быть отдельным upstream-этапом. Текущий проект фокусируется на OCR, агрегации, matching, enrichment, нормализации и экспорте.

Решение не использует облачные API и рассчитано на локальный воспроизводимый запуск.

## Quick Start

Минимальный grouped-запуск с auto reference по `input/<run_id>/name.json`, product catalog, OCR cache, summary и timing reports:

```powershell
cd lenta-cv
.\.venv\Scripts\activate

python run.py --input-root input/Test30 --grouped --use-reference --reference-mode auto --reference-dir data/reference --use-product-catalog --product-catalog data/reference/db_hack.csv --use-ocr-cache --summary-report --timing-report --initial-views 7 --max-views-per-group 10 --adaptive --early-stop --output outputs/final/group_result_test30.csv
```

Результаты смотреть здесь:

- `outputs/final/group_result_test30.csv` — финальный CSV;
- `outputs/reference_match_report.csv` — почему сработал или не сработал reference match;
- `outputs/product_catalog_match_report.csv` — matching по `db_hack.csv`;
- `outputs/group_debug_report.csv` — summary по группам;
- `outputs/group_trace/*.json` — подробный trace по каждому ценнику;
- `outputs/pipeline_summary_report.txt` и `outputs/timing_report.txt` — качество и время.

Если reference-файл не найден или `department = "unknown"`, pipeline не падает: он продолжает работать в OCR + catalog или OCR-only режиме.

## Что решает

Система формирует CSV, где одна строка соответствует одному уникальному ценнику. В строке собираются:

- название товара;
- цены без карты / с картой / акционные цены;
- скидка;
- barcode, QR-поля, id_sku;
- дата печати, служебный code, additional_info;
- цвет ценника и специальные символы;
- координаты и timestamp из входных metadata.

Ключевая идея: не пытаться идеально прочитать один плохой кадр. Pipeline собирает признаки с нескольких view одного ценника, выбирает лучшие значения, сверяет их с каталогом и reference-БД, а при недостатке уверенности оставляет поле пустым.

Семантика значений:

- `нет` — параметр точно отсутствует на ценнике, в QR или в reference-данных.
- пустая строка `""` — параметр не распознан или неизвестен.

## Ключевые идеи

- **Гибридный подход**: OCR + layout extractors + grouped aggregation + product catalog + optional reference matching.
- **Confidence-first enrichment**: reference-значения подставляются только при уверенном совпадении.
- **Fallback modes**: система может работать без reference-БД и без product catalog, но качество будет ниже.
- **Traceability**: для grouped-запуска создаются debug-отчеты и trace JSON.
- **Локальность**: OCR, matching и export выполняются локально.

## Режимы работы

### 1. OCR-only mode

Используется, когда нет ни product catalog, ни reference-БД.

Система извлекает только видимые поля:

- цены;
- скидку;
- цвет ценника;
- частичное product_name;
- barcode/QR, если они реально прочитались.

Это самый универсальный, но самый слабый режим. Если OCR не увидел поле, оно остается пустым.

### 2. OCR + Product Catalog mode

Используется `db_hack.csv`.

Система пытается сопоставить шумное OCR-название с общим каталогом товаров. При уверенном совпадении можно восстановить clean product_name.

Важно: `db_hack.csv` содержит в основном названия и коды товаров. Он не заменяет полноценную reference-БД с ценами, QR, code, id_sku, датой печати и другими полями конкретного ценника.

### 3. OCR + Product Catalog + Reference mode

Если для выбранного отдела или ролика есть reference CSV, система использует его для enrichment:

- clean product_name;
- barcode;
- id_sku;
- print_datetime;
- code;
- additional_info;
- special_symbols;
- QR fields;
- цены из reference при high confidence.

Reference используется только при уверенном совпадении. Если уверенности нет, система не делает рискованных подстановок.

## Контракт входных данных от UI

Ожидается, что UI или upstream-сервис передает backend папку запуска:

```text
input/<run_id>/
  name.json
  tag_000001/
    item_000001/
      image.jpg
      data.json
    item_000002/
      image.jpg
      data.json
  tag_000002/
    item_000001/
      image.jpg
      data.json
```

Контракт:

- `input/<run_id>/name.json` — metadata всего запуска, минимум поле `department`.
- `tag_XXXXX` — один уникальный физический ценник.
- `item_XXXXXX` — один кадр/ракурс этого ценника.
- `image.jpg` — кроп ценника в корректной ориентации.
- `data.json` — metadata конкретного view: timestamp, bbox, detector confidence, sharpness и т.п.

Пример `name.json`:

```json
{
  "department": "wine/25_2-10"
}
```

Пример `data.json`:

```json
{
  "frame_timestamp": 0,
  "bbox": {
    "x_min": 734,
    "y_min": 999.9,
    "x_max": 940.8,
    "y_max": 1240.1
  },
  "product_id_above_tag": "",
  "video_filename": "25_2-10.mp4",
  "confidence": 0.87,
  "sharpness": 112.4
}
```

Loader устойчив к вариантам:

- `bbox` может быть dict или list `[x_min, y_min, x_max, y_max]`;
- timestamp может называться `frame_timestamp`, `timestamp` или `time_ms`;
- detector score может называться `confidence`, `detector_confidence` или `score`;
- sharpness может называться `sharpness` или `blur_score`.

Если часть metadata отсутствует, pipeline продолжает работу, но view selection может быть менее точным.

## name.json и выбор reference-БД

В корне input-папки может лежать файл:

```text
input/TestFull/name.json
```

Пример:

```json
{
  "department": "wine/25_2-10"
}
```

Формат:

```text
<department>/<reference_key>
```

Где:

- `department` — широкий отдел магазина;
- `reference_key` — ключ конкретной reference-БД.

Поддерживаемые значения:

| department | reference key | Reference CSV |
|---|---:|---|
| `wine/25_2-10` | `25_2-10` | `25_2-10.csv` |
| `wine/25_12-20` | `25_12-20` | `25_12-20.csv` |
| `wine/26_12-20` | `26_12-20` | `26_12-20.csv` |
| `gastronomy/43_15` | `43_15` | `43_15.csv` |
| `dairy/49_5` | `49_5` | `49_5.csv` |
| `unknown` | пусто | reference не используется |

Папка с reference CSV задается флагом `--reference-dir`.

В текущем репозитории reference-файлы лежат в `data/reference`, поэтому для auto mode используется:

```powershell
--reference-dir data/reference
```

Если в другом окружении файлы лежат в `data/reference/references`, используйте:

```powershell
--reference-dir data/reference/references
```

Логика:

- если `department = "wine/25_2-10"`, система ищет `25_2-10.csv` в `reference-dir`;
- если файл найден, включается reference-assisted mode;
- если файл не найден или `department = "unknown"`, pipeline не падает и продолжает работу в OCR + catalog или OCR-only режиме.

Пример сообщения:

```text
Reference selection: enabled=True mode=auto department=wine/25_2-10 reference_key=25_2-10 path=.../data/reference/25_2-10.csv reason=reference_selected_by_department
```

## Необходимые локальные данные

Для полного запуска нужны локальные файлы данных. Они могут быть большими и не обязаны храниться в git.

### Product catalog

```text
data/reference/db_hack.csv
```

Ожидаемый формат:

- encoding: `cp1251`;
- delimiter: `;`;
- колонки: `fullname`, `code`.

Используется только для нормализации product_name и осторожного barcode/code enrichment при уверенном совпадении.

### Reference CSV

Файлы отдела:

```text
data/reference/25_2-10.csv
data/reference/25_12-20.csv
data/reference/26_12-20.csv
data/reference/43_15.csv
data/reference/49_5.csv
```

Или аналогичная папка, переданная через `--reference-dir`.

Reference CSV должен иметь колонки output schema. Если reference нет или он не выбран, backend продолжает работу без него.

### Input folders

Grouped input:

```text
input/<run_id>/
```

Внутри ожидаются `name.json`, `tag_*` папки, `item_*` view, `image.jpg` и `data.json`.

## Архитектура

Общая цепочка:

```text
raw image
-> preprocessing / OCR profile
-> OCR blocks
-> TagInfo Builder
-> Strategy Resolver
-> parser by tag family
-> field extraction strategy
-> QR extractor
-> ResultRow Builder
-> grouped aggregation
-> Product Catalog Resolver
-> Reference Matcher
-> Output Normalizer
-> CSV Export
```

### Preprocessing / OCR profile

Подготавливает изображение к OCR. Для белых и красных ценников используются разные OCR/preprocess profiles: жесткий threshold хорошо работает на части белых ценников, но может разрушать красную промо-область.

### OCR

Извлекает текстовые блоки, confidence и bbox. OCR blocks имеют структурированный вид:

```python
{
    "text": str,
    "confidence": float,
    "bbox": list | None,
    "source": str,
}
```

### TagInfo Builder

Определяет признаки ценника: family, format, mechanic, цвет, наличие скидки, QR/barcode, ценовые зоны и т.п.

### Strategy Resolver

Выбирает parser по типу ценника:

- `gm_6x6_regular` — белые регулярные ценники;
- `gm_6x6_red_promo` — красные промо-ценники;
- `generic` fallback.

### Field extraction strategy

Parser и shared extractors извлекают:

- `product_name`
- `price_default`
- `price_card`
- `discount_amount`
- `barcode`
- `id_sku`
- `print_datetime`
- `code`
- `additional_info`
- `color`
- `special_symbols`

### QR extractor

Пытается прочитать QR через OpenCV `QRCodeDetector`. Если QR не прочитан, QR-поля остаются пустыми. Если QR прочитан, но конкретного параметра в payload нет, поле может получить значение `нет`.

### ResultRow Builder

Собирает строку по `OUTPUT_COLUMNS` из `src/schema.py` и различает `нет` и пустое значение.

### Grouped aggregation

Обрабатывает несколько кадров одного физического ценника. Для каждого поля выбирается лучший источник из разных view. В `group_trace/*.json` сохраняется field-level trace: какое view дало какое поле и почему.

### Product Catalog Resolver

Использует `db_hack.csv` как большой каталог товарных названий. Каталог помогает превратить шумный OCR product_name в clean product_name.

Resolver строит token index и умеет разрешать конфликты через distinguishing tokens. Например, похожие позиции `PURE ALTITUDE Шардоне` и `PURE ALTITUDE Совиньон Блан` различаются по словам `шардоне`, `совиньон`, `блан`.

### Reference Matcher

Если для отдела/ролика доступна reference-БД, matcher сверяет OCR-признаки с ней:

- barcode;
- QR barcode;
- id_sku;
- price_card;
- price_default;
- discount_amount;
- color;
- product_name/catalog tokens.

При `high` confidence reference matcher подтягивает clean fields из reference. Если данных недостаточно, pipeline не делает рискованную подстановку.

Дополнительно есть безопасные правила для типичных OCR-провалов. Например, если OCR потерял ведущую цифру в цене, matcher может проверить matching-only варианты `104.99 -> 1104.99`, но не меняет output напрямую без high-confidence reference match.

### Output Normalizer

Финально нормализует CSV:

- убирает переносы строк;
- схлопывает пробелы;
- `0. 75L` -> `0.75L`;
- цены с запятой переводит в цены с точкой;
- barcode/QR barcode оставляет только цифрами;
- `нет` сохраняет как `нет`;
- пустые значения оставляет пустыми.

## Формат output CSV

Финальный CSV сохраняется в путь из `--output`. Порядок колонок задается `src/schema.py`.

Колонки:

```text
filename,
product_name,
price_default,
price_card,
price_discount,
barcode,
discount_amount,
id_sku,
print_datetime,
code,
additional_info,
color,
special_symbols,
frame_timestamp,
x_min,
y_min,
x_max,
y_max,
qr_code_barcode,
price1_qr,
price2_qr,
price3_qr,
price4_qr,
wholesale_level_1_count,
wholesale_level_1_price,
wholesale_level_2_count,
wholesale_level_2_price,
action_price_qr,
action_code_qr
```

`нет` и пустое значение имеют разную семантику. `нет` означает отсутствие параметра, пустое поле — неизвестно или не распознано.

## Установка

Основной вариант: `.venv` внутри проекта `lenta-cv`.

Windows PowerShell:

```powershell
cd lenta-cv
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

Альтернативно можно держать виртуальное окружение в корне репозитория:

```powershell
cd lenta-cv
python -m venv ..\.venv
..\.venv\Scripts\activate
pip install -r requirements.txt
```

Проект использует OpenCV, EasyOCR и PyTorch. Для ускорения OCR желательно окружение с доступным GPU, но pipeline работает и на CPU.

## Команды запуска

### Белый baseline

```powershell
python run.py --all
python -m src.checker
```

### Grouped run с auto reference по name.json

Если reference CSV лежат в `data/reference`:

```powershell
python run.py --input-root input/Test30 --grouped --use-reference --reference-mode auto --reference-dir data/reference --use-product-catalog --product-catalog data/reference/db_hack.csv --use-ocr-cache --summary-report --timing-report --initial-views 7 --max-views-per-group 10 --adaptive --early-stop --output outputs/final/group_result_test30.csv
```

### Forced reference

```powershell
python run.py --input-root input/Test30 --grouped --use-reference --reference-mode forced --reference data/reference/25_2-10.csv --use-product-catalog --product-catalog data/reference/db_hack.csv --use-ocr-cache --summary-report --timing-report --output outputs/final/group_result_forced.csv
```

### Catalog-only

```powershell
python run.py --input-root input/Test30 --grouped --reference-mode off --use-product-catalog --product-catalog data/reference/db_hack.csv --use-ocr-cache --summary-report --timing-report --initial-views 7 --max-views-per-group 10 --adaptive --early-stop --output outputs/final/group_result_catalog_only.csv
```

### OCR-only

```powershell
python run.py --input-root input/Test30 --grouped --reference-mode off --use-ocr-cache --summary-report --timing-report --initial-views 7 --max-views-per-group 10 --adaptive --early-stop --output outputs/final/group_result_ocr_only.csv
```

## Reports

После grouped-запуска создаются debug и summary artifacts:

- `outputs/group_debug_report.csv` — summary по каждой группе: views, processed views, early stop, confidence, источники полей.
- `outputs/reference_match_report.csv` — как сработал reference matcher, score, margin, reasons/warnings.
- `outputs/product_catalog_match_report.csv` — как сработал product catalog, top candidates, conflict resolution.
- `outputs/pipeline_summary_report.txt` / `.csv` — общий итог по запуску.
- `outputs/timing_report.txt` / `.csv` — время по этапам и группам.
- `outputs/group_trace/*.json` — подробный trace по каждому ценнику: candidates, final_row, field_sources, enrichment.

## Оптимизации

### View selection

Система не OCR-ит все кадры подряд. Она выбирает top-N view по quality score: detector confidence, sharpness, bbox size и diversity по времени/позиции.

### Early stop

Если после части кадров reference match стал `high`, оставшиеся view группы не обрабатываются.

### OCR cache

Повторные запуски на тех же изображениях могут брать OCR blocks из `outputs/ocr_cache`.

### Product catalog cache

Индекс `db_hack.csv` кэшируется на диск в `outputs/product_catalog_cache`, чтобы не строить token index заново каждый запуск.

### Timing report

`timing_report.txt` показывает, где тратится время. По текущим замерам основной bottleneck — OCR, поэтому уменьшение количества OCR view критично.

## Текущие результаты

Числа ниже относятся к конкретному локальному прогону из `outputs/final`. Они зависят от качества входных кропов, выбранной reference-БД, наличия product catalog, состояния OCR/cache и параметров запуска.

На этом full-запуске:

- всего групп: 97;
- обработано view: 700 из 2506;
- early stop: 8 групп;
- reference high: 15 из 97;
- enriched groups: 16;
- OCR cache hits: 259, misses: 441;
- total runtime: около 1006 секунд;
- OCR занял около 989 секунд.

Эти цифры не означают, что система идеально распознает все ценники. Они показывают, что MVP уверенно работает на части групп, где есть сильные признаки: barcode, QR, id_sku, price+discount+color или подходящая reference-БД. На плохих кадрах без надежных признаков система оставляет partial result вместо рискованного ложного матча.

Белый `gm_6x6_regular` baseline проверяется отдельным checker-ом и должен оставаться зеленым.

## Demo cases

### PURE ALTITUDE Шардоне / Совиньон Блан

Похожие товары могут иметь одинаковые price/discount/color. Product Catalog Resolver различает их через distinguishing tokens: `шардоне`, `совиньон`, `блан`.

### OCR price repair

Если OCR потерял ведущую цифру в цене, например `104.99` вместо `1104.99`, reference matcher проверяет repair variants только внутри matching. Output меняется на reference price только при high-confidence совпадении.

### BANFI

Случай, где `price_card + discount + color + большой margin` позволяют безопасно поднять reference match до high даже при шумном product_name.

### Bad OCR case

Если нет barcode/QR/id_sku, product_name мусорный, а price не дает надежного совпадения, система оставляет partial result и не подставляет случайный товар.

## Ограничения

1. **Качество OCR зависит от кропов.** Плохой фокус, блики, стекло, частичное перекрытие, сильный угол и низкое разрешение ухудшают распознавание.
2. **Без reference-БД качество ниже.** Система честно извлекает видимые поля, но не подставляет товар без уверенности.
3. **Product catalog не заменяет reference.** `db_hack.csv` помогает с названием, но не всегда содержит цены, QR, code, id_sku и дату печати.
4. **QR/barcode часто не читаются на видео.** Они могут быть слишком мелкими, смазанными или частично закрытыми.
5. **Проект ожидает grouped input.** Детекция и трекинг ценников на полном видео — отдельный upstream-этап.
6. **OCR — главный bottleneck.** Для масштабирования стоит улучшать ROI OCR, batching на GPU, модель OCR или стратегию выбора view.

## Что не коммитить

В git не нужно добавлять локальные данные и результаты прогонов:

- `input/` с пользовательскими запусками;
- `outputs/`;
- `outputs/ocr_cache/`;
- `outputs/product_catalog_cache/`;
- большие reference/db файлы вроде `db_hack.csv`, если они не предусмотрены правилами репозитория;
- временные debug-файлы и локальные virtualenv.

Эти данные зависят от запуска, могут быть тяжелыми и не являются частью исходного кода backend.

## Как масштабировать

Ближайшие направления развития:

- улучшить upstream detector/tracker, чтобы grouped input был стабильнее;
- добавить ROI OCR для конкретных зон: price, discount, barcode, product_name;
- использовать GPU batching для OCR;
- расширять parser families для новых форматов ценников;
- улучшать reference matching по отделам и типам механик;
- добавлять доменные правила только через confidence-aware matching, чтобы не создавать ложные данные.

## Структура проекта

```text
src/
  schema.py                    # OUTPUT_COLUMNS и нормализация строки
  exporter.py                  # CSV export
  price_tag_parser.py          # single-image orchestration
  ocr.py                       # OCR backend wrapper
  ocr_preprocess_profiles.py   # OCR/preprocess profiles
  tag_info.py                  # TagInfo dataclass
  tag_type.py                  # классификация типа ценника
  strategy_resolver.py         # выбор parser
  result_row_builder.py        # финальная строка ResultRow
  input_models.py              # ImageView, TagGroup, ParsedCandidate
  input_loader.py              # загрузка grouped input
  group_pipeline.py            # grouped processing
  candidate_aggregator.py      # агрегация view в одну строку
  product_catalog.py           # db_hack.csv catalog resolver
  reference_manager.py         # выбор reference по name.json
  reference_store.py           # загрузка reference CSV
  reference_matcher.py         # confidence-aware reference matching
  output_normalizer.py         # финальная нормализация output CSV
  pipeline_summary.py          # summary report
  timing.py                    # timing report
  qr_validation.py             # QR vs visible fields validation
  checker.py                   # baseline checker
  extractors/                  # shared field extractors
  parsers/                     # parser classes by tag family
  utils/                       # bbox/price/barcode helpers
```

## Итог

Это MVP не про “магическое распознавание любого ценника с одного кадра”, а про инженерный, воспроизводимый и расширяемый pipeline:

- работает локально;
- использует несколько view одного ценника;
- сохраняет confidence/debug trace;
- поддерживает OCR-only fallback;
- усиливается catalog/reference данными, когда они доступны;
- не подставляет данные без достаточной уверенности.

