## Допфича: UI с отображением метрик

### Сценарий на демо (FX-1)

Просмотрите дашборд по адресу {base_url}/metabase

Логин/пароль от metabase:

```
admin@example.com
metabase12
```

В фильтрах дашборда необходимо выбрать имя эксперимента и время начала/окончания периода за которые смотрятся метрики
В отдельных дашбордах надо выбрать имя варианта чтобы посчитать метрики и гранулярность для дашборда с таймсериями

Во вкладке "итоги A/B тестирования" есть диаграммы метрик по таймсериям и по каждому варианту:
* Диаграмма с динамикой метрик для каждого варианта
* Диаграмма с общими значениями всех метрик для каждого варианта (на ней можно смотреть разрезы по payload метрик)
* Диаграмма с количеством уникальных субъектов для каждого варианта

Во вкладке "технические диаграммы" есть диаграммы для мониторинга идущего A/B тестирования:
* долю отклонённых событий и причины (процентное соотношение причин на круговой диаграмме);
* доля дубликатов (среди отклоненных)
* степень полноты атрибуции
* перекос трафика: фактическое распределение показов по вариантам против ожидаемого по весам.

---

### Тестовые данные и сценарий эмулятора

#### 1. Запуск seed

```bash
python "demo/FX-1-2 UI additional_feature UI/seed_data_ui.py"
```

Создаёт:
- 2 пользователя (ui_experimenter@demo.com / ui_approver@demo.com, пароль Demo1234!x)
- 2 типа событий: `ui_exposure`, `ui_click` (зависит от ui_exposure), оба с payload `{country, device}`
- 3 метрики: `ui_click_conversion` (PRIMARY), `ui_exposure_count`, `ui_click_count`
- 1 feature flag: `ui_banner_style` (default=classic)
- 1 эксперимент "Тест стиля баннера" (RUNNING): classic vs modern, 50/50

#### 2. Запуск сценариев эмулятора

После seed'а нужно запустить 4 сценария эмулятора последовательно — по одному на каждую комбинацию country/device.
Каждый сценарий генерирует отдельную группу субъектов, поэтому на один decision_id приходится ровно одна пара exposure+click без дублирования.

Все сценарии отправляются в `POST http://localhost/emulator/scenarios`. Запускайте их последовательно (дождитесь завершения предыдущего).

**Сценарий 1: RU + mobile** (50 субъектов)

```json
{
  "scenario_name": "UI banner: RU mobile",
  "subjects_count": 50,
  "experiment": {
    "feature_flag_key": "ui_banner_style",
    "time_delay_seconds": 1,
    "time_variation": 0,
    "variants": [
      {
        "feature_flag_value": "classic",
        "events": [
          {"event_type": "ui_exposure", "time_delay_seconds": 0, "time_variation": 0, "probability": 1.0, "payload": {"country": "RU", "device": "mobile"}},
          {"event_type": "ui_click",    "time_delay_seconds": 0, "time_variation": 0, "probability": 0.5, "payload": {"country": "RU", "device": "mobile"}}
        ]
      },
      {
        "feature_flag_value": "modern",
        "events": [
          {"event_type": "ui_exposure", "time_delay_seconds": 0, "time_variation": 0, "probability": 1.0, "payload": {"country": "RU", "device": "mobile"}},
          {"event_type": "ui_click",    "time_delay_seconds": 0, "time_variation": 0, "probability": 0.7, "payload": {"country": "RU", "device": "mobile"}}
        ]
      }
    ]
  }
}
```

**Сценарий 2: RU + desktop** (50 субъектов)

```json
{
  "scenario_name": "UI banner: RU desktop",
  "subjects_count": 50,
  "experiment": {
    "feature_flag_key": "ui_banner_style",
    "time_delay_seconds": 1,
    "time_variation": 0,
    "variants": [
      {
        "feature_flag_value": "classic",
        "events": [
          {"event_type": "ui_exposure", "time_delay_seconds": 0, "time_variation": 0, "probability": 1.0, "payload": {"country": "RU", "device": "desktop"}},
          {"event_type": "ui_click",    "time_delay_seconds": 0, "time_variation": 0, "probability": 0.4, "payload": {"country": "RU", "device": "desktop"}}
        ]
      },
      {
        "feature_flag_value": "modern",
        "events": [
          {"event_type": "ui_exposure", "time_delay_seconds": 0, "time_variation": 0, "probability": 1.0, "payload": {"country": "RU", "device": "desktop"}},
          {"event_type": "ui_click",    "time_delay_seconds": 0, "time_variation": 0, "probability": 0.6, "payload": {"country": "RU", "device": "desktop"}}
        ]
      }
    ]
  }
}
```

**Сценарий 3: US + mobile** (50 субъектов)

```json
{
  "scenario_name": "UI banner: US mobile",
  "subjects_count": 50,
  "experiment": {
    "feature_flag_key": "ui_banner_style",
    "time_delay_seconds": 1,
    "time_variation": 0,
    "variants": [
      {
        "feature_flag_value": "classic",
        "events": [
          {"event_type": "ui_exposure", "time_delay_seconds": 0, "time_variation": 0, "probability": 1.0, "payload": {"country": "US", "device": "mobile"}},
          {"event_type": "ui_click",    "time_delay_seconds": 0, "time_variation": 0, "probability": 0.6, "payload": {"country": "US", "device": "mobile"}}
        ]
      },
      {
        "feature_flag_value": "modern",
        "events": [
          {"event_type": "ui_exposure", "time_delay_seconds": 0, "time_variation": 0, "probability": 1.0, "payload": {"country": "US", "device": "mobile"}},
          {"event_type": "ui_click",    "time_delay_seconds": 0, "time_variation": 0, "probability": 0.8, "payload": {"country": "US", "device": "mobile"}}
        ]
      }
    ]
  }
}
```

**Сценарий 4: US + desktop** (50 субъектов)

```json
{
  "scenario_name": "UI banner: US desktop",
  "subjects_count": 50,
  "experiment": {
    "feature_flag_key": "ui_banner_style",
    "time_delay_seconds": 1,
    "time_variation": 0,
    "variants": [
      {
        "feature_flag_value": "classic",
        "events": [
          {"event_type": "ui_exposure", "time_delay_seconds": 0, "time_variation": 0, "probability": 1.0, "payload": {"country": "US", "device": "desktop"}},
          {"event_type": "ui_click",    "time_delay_seconds": 0, "time_variation": 0, "probability": 0.45, "payload": {"country": "US", "device": "desktop"}}
        ]
      },
      {
        "feature_flag_value": "modern",
        "events": [
          {"event_type": "ui_exposure", "time_delay_seconds": 0, "time_variation": 0, "probability": 1.0, "payload": {"country": "US", "device": "desktop"}},
          {"event_type": "ui_click",    "time_delay_seconds": 0, "time_variation": 0, "probability": 0.65, "payload": {"country": "US", "device": "desktop"}}
        ]
      }
    ]
  }
}
```

Ожидаемые данные (суммарно по 4 сценариям):
- 200 субъектов (4 x 50), 200 exposure, ~100-120 click
- Разрезы по `country`: RU (~100 субъектов), US (~100 субъектов)
- Разрезы по `device`: mobile (~100 субъектов), desktop (~100 субъектов)
- Вариант modern имеет более высокую конверсию (~65-70%) чем classic (~45-50%)

#### 3. Что проверять в UI

1. Открыть Metabase: `http://localhost/metabase`
2. Выбрать эксперимент "Тест стиля баннера"
3. Убедиться что метрики отображаются для обоих вариантов (classic / modern)
4. На графике общих метрик проверить разрезы:
   - По `country`: RU vs US
   - По `device`: mobile vs desktop -- mobile должен иметь чуть более высокую конверсию
5. Вариант modern должен показывать более высокий ui_click_conversion чем classic

Опционально -
В сваггере получить decision ID на ключ ui_banner_style с любым subject_id
POST /api/v1/decision
```
{
  "id": "strineewq23132131g",
  "subject_attr": {
    "additionalProp1": {}
  },
  "flags_keys": [
    "ui_banner_style"
  ]
}
```

и отправить невалидное событие или событие-дубликат, а также событие click без экспозиции.

невалидное
```
{
  "events": [
    {
      "event_type": "click-not-found",
      "decision_id": "8809e604-0896-4310-a98b-b87ef67c0cc9",
      "payload": {
        "additionalProp1": {}
      }
    }
  ]
}
```

click без экспозиции-

```
{
  "events": [
    {
      "event_type": "ui_click",
      "decision_id": "8809e604-0896-4310-a98b-b87ef67c0cc9",
      "payload": {"country": "US", "device": "desktop"}
    }
  ]
}
```

дубликат
```
{
  "events": [
    {
      "event_type": "ui_click",
      "decision_id": "8809e604-0896-4310-a98b-b87ef67c0cc9",
      "payload": {"country": "US", "device": "desktop"}
    }
  ]
}
```


Потом еще раз посмотреть UI, должны отобразиться rejected событие и pending событие.  

### Ограничения (FX-2)
* Если в базе есть эксперименты с одинаковыми именами, вывод метрик в UI может работать некорректно (не тот эксперимент)
* Нет фильтрации имен вариантов в UI - на отдельных дашбордах в выпадающем списке доступны имена вариантов других экспериментов
* Дата и время задаются вручную - metabase не позволяет задавать время в фильтрах на дащборде, только дату. Поэтому дата+время задается как текстовое поле.
* Metabase подключается к postgresql и делает запросы с хранимой процедурой - плохое решение в плане архитектуры системы, но никак не влияет на функциональность UI
* Разрезы по payload (страна, устройство) можно смотреть только на графике общих метрик (таймсерии-нельзя)
* Разрезы payload считаются по payload ивента, а не по payload subject а . Это сделано потому что так сказано в формулировке задания доп фичи.