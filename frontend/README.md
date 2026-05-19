# LentaCV Frontend

Mock frontend для проекта LentaCV. Интерфейс демонстрирует основной пользовательский сценарий:

```text
выбор режима -> загрузка видео -> выбор отдела -> обработка -> результаты -> экспорт CSV
```

Backend OCR/matching pipeline находится в соседней папке `../lenta-cv` и сейчас запускается через CLI. Этот frontend пока работает на mock API.

## Запуск

```bash
cd frontend
npm install
npm run dev
```

Production build:

```bash
npm run build
```

## Режимы

- **Режим обработки видео** - загрузка видео, выбор department, имитация обработки, просмотр результатов.
- **Режим дообучения** - UI-заглушка для будущей ручной разметки и подготовки обучающих данных.

## Mock API

Компоненты импортируют API только из:

```text
src/api/client.ts
```

Сейчас `client.ts` проксирует вызовы в `mockClient.ts`. Для подключения реального backend достаточно заменить реализацию в `client.ts` на `fetch`.

## Будущий backend API contract

```text
POST /api/runs
GET  /api/runs/{run_id}/status
GET  /api/runs/{run_id}/summary
GET  /api/runs/{run_id}/results
GET  /api/runs/{run_id}/csv
```

`department` из UI в будущем должен записываться backend-ом в:

```text
input/<run_id>/name.json
```

Пример:

```json
{
  "department": "wine/25_2-10"
}
```
