# team/ — «Рудник под лимитом»

Код решения. Запускается вместе с платформой командой `make up` из корня репозитория (оверлей [compose.yml](compose.yml)).

**Как всё работает — подробно: [HOW-IT-WORKS.md](HOW-IT-WORKS.md).**

```
                 Ditto (двойники kz.limit:*)
                 ▲ MQTT telemetry/<двойник>      ▲ HTTP: чтение         ▲ HTTP: чтение, запись control
                 │                               │                      │
 limit-simulator ┘  физика комплекса ◄── уставки плана ── limit-planner   limit-web (3D, nginx-прокси)
                                                  (LP на 24 ч)
 Ditto ── MQTT-события ──► Telegraf ──► InfluxDB ──► Grafana (дашборд «Рудник под лимитом»)
```

| Файл | Что делает |
|---|---|
| [engine/params.py](engine/params.py) | Все параметры комплекса и сценариев, единицы и смысл |
| [engine/setup_twins.py](engine/setup_twins.py) | Создаёт 23 двойника в Ditto (идемпотентно; двойник `control` со сценариями не перезаписывает) |
| [engine/simulator.py](engine/simulator.py) | Шаг модели: карьер → дробилка → склад → мельницы → флотация → сгуститель → хвостохранилище; вода, энергия, блокировки, САОН. Публикует состояние в MQTT, читает `control` и `planner` из Ditto |
| [engine/lp.py](engine/lp.py) | Линейная программа суточного плана (SciPy/HiGHS), её вариант «по отделам», теневые цены |
| [engine/planner.py](engine/planner.py) | Сервис модуля: собирает состояние из Ditto, решает, формирует рекомендации и публикует их в двойник `planner` |
| [engine/platform_io.py](engine/platform_io.py) | MQTT и Ditto HTTP |
| [web/](web/) | 3D-страница (`index.html`, `app.js`, `style.css`), Three.js r160 в `vendor/`, конфигурация nginx-прокси |

Параметры запуска (в `deploy/compose/.env` или окружении): `SIM_SPEEDUP` (по умолчанию 60 — минута реального времени = час модели), `SIM_START_HOUR` (16.5), `LIMIT_WEB_PORT` (8100).
