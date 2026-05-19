# LentaCV

Гибридный OCR/reference pipeline и демонстрационный UI для распознавания ценников Ленты с видеопотока робота.

LentaCV состоит из двух независимых частей:

- `lenta-cv/` - backend/OCR pipeline, который обрабатывает кропы ценников, агрегирует несколько ракурсов одного ценника, сопоставляет результат с каталогом/reference-БД и формирует CSV.
- `frontend/` - демонстрационный React/Vite интерфейс для выбора режима, загрузки видео, выбора отдела, просмотра результатов и экспорта CSV.

Сейчас frontend работает на mock API. Backend работает отдельно через CLI. Интеграция планируется через HTTP API-слой поверх текущего OCR pipeline.

## Структура Репозитория

```text
lenta_hack/
  README.md

  lenta-cv/
    README.md
    run.py
    src/
    data/
    input/
    outputs/
    requirements.txt

  frontend/
    README.md
    package.json
    src/
      App.tsx
      api/
      components/
      pages/
      types/
      data/
```

## Части Проекта

### Backend / OCR Pipeline

Папка: `lenta-cv/`

Backend принимает grouped input и выполняет полный цикл распознавания:

```text
input/<run_id>/name.json
input/<run_id>/tag_*/item_*/image.jpg
input/<run_id>/tag_*/item_*/data.json
```

Что делает backend:

- читает `name.json` и определяет отдел;
- выбирает reference-БД по `department`;
- обрабатывает кропы ценников;
- запускает OCR;
- определяет тип ценника;
- извлекает поля ценника;
- агрегирует несколько view одного ценника;
- сопоставляет шумное OCR-название с `db_hack.csv`;
- обогащает результат через reference CSV при высокой уверенности;
- нормализует итоговый CSV;
- создает debug, summary и timing reports.

Подробное описание backend находится в [lenta-cv/README.md](lenta-cv/README.md).

### Frontend / UI

Папка: `frontend/`

Frontend - отдельное React/Vite приложение. Сейчас оно работает на mock API и показывает продуктовый сценарий:

```text
выбор режима -> загрузка видео -> выбор department -> обработка -> результаты -> экспорт CSV
```

Frontend не запускает OCR напрямую и пока не отправляет реальные файлы в backend. Его задача на текущем этапе - показать пользовательский путь и будущий API-контракт.

Подробное описание frontend находится в [frontend/README.md](frontend/README.md).

## Основной Пользовательский Сценарий

1. Пользователь открывает frontend.
2. Выбирает режим обработки видео.
3. Загружает видео.
4. Выбирает отдел, например `wine/25_2-10`.
5. Frontend создает запуск.
6. Backend в будущем должен подготовить структуру `input/<run_id>/`.
7. Backend запускает OCR/matching pipeline.
8. Пользователь видит результаты: уверенные совпадения, частичные распознавания и позиции для проверки.
9. Пользователь экспортирует итоговый CSV.

Сейчас шаги 5-9 во frontend имитируются mock API.

## Как Frontend И Backend Должны Быть Связаны

Планируемая интеграция:

```text
frontend
-> HTTP API
-> backend wrapper around lenta-cv/run.py and grouped pipeline
-> outputs CSV/reports
-> frontend results view
```

Backend уже умеет работать с локальной grouped input-структурой. Для полноценной интеграции нужен тонкий API-слой, который:

- принимает видео и выбранный `department`;
- создает `run_id`;
- запускает upstream-этап детекции/трекинга или принимает уже готовые кропы;
- формирует `input/<run_id>/name.json`;
- кладет кропы в `tag_*/item_*`;
- запускает backend pipeline;
- отдает статус, summary, results и CSV во frontend.

Важно: этот репозиторий уже содержит OCR/matching backend и mock frontend. Детекция и трекинг по полному видео могут быть отдельным upstream-этапом.

## Будущий API-Контракт

Минимальный контракт для подключения frontend к backend:

```text
POST /api/runs
GET  /api/runs/{run_id}/status
GET  /api/runs/{run_id}/summary
GET  /api/runs/{run_id}/results
GET  /api/runs/{run_id}/csv
```

Ожидаемая логика:

### `POST /api/runs`

Создает запуск обработки.

Вход:

```json
{
  "department": "wine/25_2-10",
  "fileName": "shelf_video.mp4"
}
```

Выход:

```json
{
  "id": "run_001",
  "department": "wine/25_2-10",
  "fileName": "shelf_video.mp4",
  "status": "uploaded",
  "progress": 0,
  "createdAt": "2026-05-19T00:00:00Z"
}
```

### `GET /api/runs/{run_id}/status`

Возвращает статус обработки:

```json
{
  "id": "run_001",
  "status": "processing",
  "progress": 64
}
```

### `GET /api/runs/{run_id}/summary`

Возвращает агрегированную статистику:

```json
{
  "totalTags": 97,
  "fullyMatched": 15,
  "partial": 30,
  "needsReview": 52,
  "failed": 0,
  "runtimeSeconds": 1006.54
}
```

### `GET /api/runs/{run_id}/results`

Возвращает список распознанных ценников.

### `GET /api/runs/{run_id}/csv`

Отдает итоговый CSV.

## Формат Input Для Backend

Backend ожидает grouped input:

```text
input/Test30/
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

Где:

- `tag_XXXXX` - один уникальный физический ценник;
- `item_XXXXXX` - один кадр/ракурс этого ценника;
- `image.jpg` - кроп ценника;
- `data.json` - метаданные кадра;
- `name.json` - метаданные входной пачки, включая отдел.

Пример `name.json`:

```json
{
  "department": "wine/25_2-10"
}
```

Поддерживаемые значения `department`:

- `wine/25_2-10`
- `wine/25_12-20`
- `wine/26_12-20`
- `gastronomy/43_15`
- `dairy/49_5`
- `unknown`

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

`data.json` может быть неполным. Loader backend устойчив к разным вариантам названий ключей, но чем больше полезных metadata, тем лучше работает выбор лучших view.

## Два Уровня Масштабируемости

В LentaCV масштабируемость обеспечивается двумя независимыми уровнями. Их важно не смешивать.

### 1. Уровень Физического Ценника: `tag/item` Grouping

В видеопотоке робот может видеть один и тот же ценник несколько раз: с разных ракурсов, в разном фокусе, с бликами или частичным смазом. Поэтому backend не считает один кадр окончательным результатом.

Структура:

```text
tag_000001/
  item_000001/
    image.jpg
    data.json
  item_000002/
    image.jpg
    data.json
  item_000003/
    image.jpg
    data.json
```

Семантика:

- `tag_000001` - один физический ценник на полке;
- `item_000001`, `item_000002`, `item_000003` - разные кадры, ракурсы или view этого же ценника;
- каждый `item_*` обрабатывается как отдельное изображение;
- затем grouped pipeline агрегирует кандидатов в одну итоговую строку CSV.

Этот уровень отвечает за устойчивость к видео: если на одном кадре плохо читается название, на другом может прочитаться цена, на третьем - barcode или QR. Aggregator выбирает лучшие значения и сохраняет trace, из какого view пришло каждое поле.

Итог: один `tag_*` должен дать одну строку в финальном CSV.

### 2. Уровень Формата Ценника: Parser Family

После OCR backend определяет формат/тип ценника и выбирает подходящий parser. Это отдельная концепция, не связанная напрямую с количеством кадров.

Сейчас поддерживаются:

- `gm_6x6_regular` - белый регулярный 6x6 ценник;
- `gm_6x6_red_promo` - красный промо 6x6 ценник;
- `generic` - fallback parser, если формат не удалось определить уверенно.

Формат ценника отвечает за:

- выбор parser-а;
- layout-правила;
- OCR/preprocess profile;
- извлечение `price_default`, `price_card`, `discount_amount`, `product_name`;
- правила для absent-полей, где `нет` означает точное отсутствие параметра;
- особенности красных/белых ценников.

Например:

```text
tag_000001
  item_000001 -> OCR -> detected family: gm_6x6_red_promo
  item_000002 -> OCR -> detected family: gm_6x6_red_promo
  item_000003 -> OCR -> detected family: gm_6x6_red_promo
```

Затем все результаты этих `item_*` агрегируются на уровне физического ценника `tag_000001`.

В будущем можно добавлять новые parser families, например:

- другие размеры ценников;
- желтые ценники;
- новые промо-механики;
- категории с другой версткой;
- ценники с оптовыми уровнями.

При этом grouped input останется тем же: `tag_*` как физический ценник, `item_*` как кадры этого ценника.

### Коротко

```text
tag/item grouping = как собрать несколько кадров одного физического ценника в одну строку

parser family = как понять layout ценника и какими правилами извлекать поля
```

Эти уровни независимы: можно улучшать агрегацию по видео, не меняя parser-ы; и можно добавлять новые форматы ценников, не меняя контракт `tag/item`.

## Выбор Reference-БД По `name.json`

Backend умеет выбирать reference CSV по `department`.

Примеры:

| `department` | Reference CSV |
|---|---|
| `wine/25_2-10` | `25_2-10.csv` |
| `wine/25_12-20` | `25_12-20.csv` |
| `wine/26_12-20` | `26_12-20.csv` |
| `gastronomy/43_15` | `43_15.csv` |
| `dairy/49_5` | `49_5.csv` |
| `unknown` | reference не используется |

Если reference-файл не найден или отдел равен `unknown`, backend не падает. Он продолжает работу в OCR + product catalog или OCR-only режиме.

## Запуск Backend

Перейти в backend:

```powershell
cd lenta-cv
```

Создать окружение:

```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

Проверить белый baseline:

```powershell
python run.py --all
python -m src.checker
```

Grouped run с auto reference по `name.json`:

```powershell
python run.py --input-root input/Test30 --grouped --use-reference --reference-mode auto --reference-dir data/reference --use-product-catalog --product-catalog data/reference/db_hack.csv --use-ocr-cache --summary-report --timing-report --initial-views 7 --max-views-per-group 10 --adaptive --early-stop --output outputs/final/group_result_test30.csv
```

Catalog-only режим:

```powershell
python run.py --input-root input/Test30 --grouped --reference-mode off --use-product-catalog --product-catalog data/reference/db_hack.csv --use-ocr-cache --summary-report --timing-report --output outputs/final/group_result_catalog_only.csv
```

OCR-only режим:

```powershell
python run.py --input-root input/Test30 --grouped --reference-mode off --use-ocr-cache --summary-report --timing-report --output outputs/final/group_result_ocr_only.csv
```

## Запуск Frontend

Перейти во frontend:

```powershell
cd frontend
```

Установить зависимости:

```powershell
npm install
```

Запустить dev server:

```powershell
npm run dev
```

Обычно Vite поднимается на:

```text
http://localhost:5173/
```

Собрать production build:

```powershell
npm run build
```

Если `npm` не найден, нужно установить Node.js LTS и заново открыть терминал.

## Демо-Режим Сейчас

Сейчас две части проекта работают независимо:

- backend запускается из `lenta-cv/` через CLI;
- frontend запускается из `frontend/` и использует mock API.

Frontend показывает демо-данные из реальных сценариев проекта:

- уверенно сопоставленные ценники;
- частичный OCR;
- позиции, требующие проверки;
- mock summary;
- mock issues;
- mock CSV export.

Это сделано специально, чтобы можно было показать продуктовый сценарий до подключения HTTP API.

## Локальные Данные И `.gitignore`

Для полноценного backend-запуска нужны локальные данные:

- `lenta-cv/input/<run_id>/` - входные grouped-кропы;
- `lenta-cv/data/reference/db_hack.csv` - общий каталог товаров;
- `lenta-cv/data/reference/*.csv` - reference-БД отделов;
- `lenta-cv/outputs/` - результаты прогонов, кэши и отчеты.

Эти файлы могут быть большими и зависят от локального запуска. Обычно их не нужно коммитить:

- `input/`
- `outputs/`
- OCR cache
- product catalog cache
- большие `db_hack.csv` и reference CSV, если они не предназначены для хранения в репозитории
- `node_modules/`
- `.venv/`

## Ограничения

1. **Frontend пока mock.** Он не отправляет видео в backend и не запускает OCR.
2. **Backend ожидает grouped input.** Детекция и трекинг ценников по полному видео могут быть upstream-этапом.
3. **OCR зависит от качества кропов.** Смаз, блики, стекло, сильный угол и маленький QR/barcode ухудшают результат.
4. **Reference-БД повышает качество, но не обязательна.** Без reference система работает честно, но слабее.
5. **Product catalog не заменяет reference.** `db_hack.csv` помогает с product_name, но не содержит всех полей ценника.
6. **Система не должна делать ложные high-match.** Если признаков недостаточно, результат остается partial, а поля остаются пустыми.

Семантика output:

- `нет` - параметр точно отсутствует;
- пустая строка - параметр неизвестен или не распознан.

## Roadmap

Что осталось подключить:

- HTTP API над текущим backend pipeline;
- реальную загрузку видео из frontend;
- создание `input/<run_id>/name.json` из выбранного department;
- upstream-этап детекции/трекинга и нарезки кропов;
- отображение реального progress backend-а;
- чтение реальных CSV/results/reports во frontend;
- экран ручной проверки спорных ценников;
- сохранение corrections для будущего улучшения OCR/parsers;
- оптимизация OCR времени через ROI OCR, batching и GPU.

## Итог

LentaCV - это не попытка идеально распознать любой ценник с одного кадра. Это воспроизводимый MVP с инженерной архитектурой:

- OCR по кропам ценников;
- агрегация нескольких ракурсов;
- product catalog matching;
- optional reference-assisted enrichment;
- confidence-aware правила;
- нормализация CSV;
- debug и timing reports;
- отдельный mock frontend для демонстрации пользовательского сценария.

Проект уже разделен так, чтобы backend можно было развивать независимо от UI, а frontend позже подключить к реальному API без переписывания OCR pipeline.
