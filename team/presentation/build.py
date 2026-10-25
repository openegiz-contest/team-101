"""
Builds the presentation of «Рудник под лимитом» from one source in two
languages: presentation.pdf (Russian, the Submission's main one) and
presentation.en.pdf (English) in the repository root.

    python3 team/presentation/build.py            # HTML + PDF
    python3 team/presentation/build.py --html     # HTML only

PDF needs Chrome or Chromium: set CHROME=/path/to/chrome, or have one of
google-chrome, chromium, chromium-browser on PATH. Screenshots in img/ are
taken from the running Stand (make up) at 1920×1080.
"""

import html
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
LANG = "ru"


def t(ru, en):
    return ru if LANG == "ru" else en


def esc(s):
    return html.escape(s, quote=False)


# Copper per model day, t: optimizer plan vs «each department for itself»,
# and the gain in %, as `make evaluate` prints it (computed there from
# unrounded tonnes). Same simulator, a model day from 16:30
# (team/engine/evaluate.py).
RESULTS = [
    (("Без ограничений", "No limits"), 244, 241, 1.4, ("", "")),
    (("Маловодный год", "Dry year"), 244, 212, 15.1, ("блокировка по воде 18 ч", "water interlock 18 h")),
    (("Вечерний пик", "Evening grid peak"), 237, 221, 7.3, ("6 отключений САОН", "6 load-shedding trips")),
    (("Маловодный год + пик", "Dry year + peak"), 237, 201, 18.0, ("САОН ×6, блокировка 13\u00a0ч", "6 trips, interlock 13 h")),
    (("Мельница №2 на ремонте", "Mill 2 under repair"), 122, 120, 1.4, ("", "")),
    (("Твёрдая руда, забой 3", "Hard ore, face 3"), 226, 224, 1.1, ("", "")),
]

TEAM = [
    ("khusrav11", ("Модель комплекса: симулятор и двойники", "Complex model: simulator and twins")),
    ("BlackIc32007", ("Модуль-оптимизатор суточного плана", "Daily plan optimizer module")),
    ("bekbolatnurmas-coder", ("3D-визуализация: Three.js и Unity-панель Grafana", "3D visualization: Three.js and the Grafana Unity panel")),
    ("Dauka-dr", ("Интеграция, Grafana, документация, презентация", "Integration, Grafana, docs, presentation")),
]


def slide(body, cls=""):
    return f'<section class="slide {cls}">{body}<div class="foot">{t("Рудник под лимитом", "Mine Under Limits")} · team-101 · OpenEgiz</div></section>'


def head(kicker, title):
    return f'<div class="kicker">{esc(kicker)}</div><h2>{esc(title)}</h2>'


def s_title():
    return slide(f"""
      <div class="title-wrap">
        <div class="kicker">{t("Digital Mine on OpenEgiz · 2026", "Digital Mine on OpenEgiz · 2026")}</div>
        <h1>{t("Рудник под лимитом", "Mine Under Limits")}</h1>
        <p class="lead">{t(
            "Цифровой двойник медного горно-обогатительного комплекса, который помогает диспетчеру перестроить суточный план, когда урезают воду или электроэнергию",
            "A digital twin of a copper mine and concentrator that helps the dispatcher re-plan the day when water or power is cut")}</p>
        <div class="team-line">{" · ".join(esc(u) for u, _ in TEAM)}</div>
      </div>
      <img class="title-img" src="img/clean-3d.jpg" alt="">
    """, "title")


def s_problem():
    cards = [
        (t("Вода", "Water"), t(
            "Центральный и Восточный Казахстан бедны водой, а обогатительная фабрика — один из крупнейших её потребителей: ~0,5 м³ свежей воды на тонну руды.",
            "Central and East Kazakhstan are short of water, and a concentrator is one of its largest users: ~0.5 m³ of fresh water per tonne of ore.")),
        (t("Электроэнергия", "Power"), t(
            "Энергосистема работает на пределе. В вечерний пик лимит мощности снижается, а превышение — это отключение мельницы автоматикой САОН.",
            "The national grid runs at its limit. In the evening peak the capacity limit drops, and exceeding it trips a mill by automatic load shedding.")),
        (t("Разрозненные отделы", "Separate departments"), t(
            "Карьер, фабрика и хвостовое хозяйство планируют каждый свой участок. Когда приходит ограничение, план режут «на глаз» и пропорционально.",
            "The pit, the plant and the tailings each plan their own area. When a limit arrives, the plan is cut by eye and in proportion.")),
    ]
    body = "".join(f'<div class="card"><h3>{esc(a)}</h3><p>{esc(b)}</p></div>' for a, b in cards)
    return slide(head(t("Почему", "Why"), t(
        "Ограничения по воде и энергии бьют по всему комплексу сразу",
        "Water and power limits hit the whole complex at once")) + f'<div class="cards3">{body}</div>' +
        f'<p class="note">{t("Ограничения будут только ужесточаться, а решения сегодня принимаются по отделам.", "The limits will only tighten, while decisions today are made department by department.")}</p>')


def s_concept():
    rows = [
        (t("Объект", "Object"), t(
            "Медно-порфировый комплекс полного цикла: карьер (3 забоя), дробилка, конвейер, склад, фабрика (2 линии измельчения, флотация), сгуститель, хвостохранилище с оборотной водой, водозабор, подстанция",
            "A full-cycle porphyry copper complex: open pit (3 faces), crusher, conveyor, stockpile, concentrator (2 grinding lines, flotation), thickener, tailings dam with water reclaim, water intake, substation")),
        (t("Пользователь", "User"), t(
            "Начальник производственно-диспетчерского отдела, который составляет суточный и сменный план",
            "The head of the production dispatch office, who draws up the daily and shift plan")),
        (t("Решение", "Decision"), t(
            "Как перестроить план добычи и переработки при ограничении: сколько руды и откуда добывать, какую загрузку держать на мельницах, сколько воды возвращать из пруда — и сколько меди стоит каждое решение",
            "How to rebuild the mining and processing plan under a limit: how much ore to dig and where, how hard to load the mills, how much water to reclaim from the pond — and what each choice costs in copper")),
        (t("Реальность", "Real or fictional"), t(
            "Объект вымышленный, по масштабу похож на сульфидную фабрику Актогая; содержание, извлечение и водопотребление сверены с открытыми данными KAZ Minerals",
            "Fictional, at the scale of an Aktogay sulphide concentrator; grade, recovery and water use checked against open KAZ Minerals data")),
    ]
    body = "".join(f'<div class="row"><div class="lbl">{esc(a)}</div><div>{esc(b)}</div></div>' for a, b in rows)
    return slide(head(t("Концепция", "Concept"), t(
        "Один двойник на весь комплекс — от забоя до хвостохранилища",
        "One twin for the whole complex — from pit face to tailings dam")) + f'<div class="rows">{body}</div>')


def box(x, y, w, title, sub, cls=""):
    return (f'<g class="node {cls}"><rect x="{x}" y="{y}" width="{w}" height="74" rx="10"/>'
            f'<text x="{x + w / 2}" y="{y + 31}" class="nt">{esc(title)}</text>'
            f'<text x="{x + w / 2}" y="{y + 55}" class="ns">{esc(sub)}</text></g>')


def arrow(d, cls):
    return f'<path d="{d}" class="fl {cls}" marker-end="url(#a-{cls})"/>'


def s_complex():
    W = 180
    svg = f"""
    <svg viewBox="0 0 1440 520" class="diagram">
      <defs>
        <marker id="a-ore" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#d08a4e"/></marker>
        <marker id="a-water" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#4aa3e8"/></marker>
        <marker id="a-power" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#e7c64a"/></marker>
        <marker id="a-slurry" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#9aa4b2"/></marker>
      </defs>
      {arrow("M210,77 L250,77", "ore")}
      {arrow("M430,77 L470,77", "ore")}
      {arrow("M650,77 L690,77", "ore")}
      {arrow("M870,77 L910,77", "ore")}
      {arrow("M1090,77 L1130,77", "ore")}
      {arrow("M1000,114 L1000,226", "slurry")}
      {arrow("M1090,263 L1130,263", "slurry")}
      {arrow("M1220,300 L1220,406", "water")}
      {arrow("M1130,443 L870,443", "water")}
      {arrow("M650,443 L690,443", "water")}
      {arrow("M780,406 L780,118", "water")}
      <path d="M120,406 L120,170 L1000,170" class="fl power"/>
      {arrow("M120,170 L120,118", "power")}
      {arrow("M340,170 L340,118", "power")}
      {arrow("M740,170 L740,118", "power")}
      {arrow("M960,170 L960,118", "power")}
      {arrow("M210,470 L470,470", "power")}
      {box(30, 40, W, t("Карьер", "Open pit"), t("3 забоя · 3 сорта", "3 faces · 3 ore types"))}
      {box(250, 40, W, t("Дробилка", "Crusher"), t("≤ 3 600 т/ч", "≤ 3,600 t/h"))}
      {box(470, 40, W, t("Склад", "Stockpile"), t("60 тыс. т · 3 штабеля", "60 kt · 3 piles"))}
      {box(690, 40, W, t("Измельчение", "Grinding"), t("2 линии × 22 МВт", "2 lines × 22 MW"), "hot")}
      {box(910, 40, W, t("Флотация", "Flotation"), t("извл. 85–89 %", "recovery 85–89%"))}
      {box(1130, 40, W + 100, t("Концентрат", "Concentrate"), t("24 % Cu · т меди/сутки", "24% Cu · t Cu per day"), "out")}
      {box(910, 226, W, t("Сгуститель", "Thickener"), t("55 или 62 % тв.", "55 or 62% solids"))}
      {box(1130, 226, W + 100, t("Хвостохранилище", "Tailings dam"), t("пруд 3,2 млн м³", "pond 3.2 Mm³"))}
      {box(1130, 406, W + 100, t("Насосы оборотной воды", "Reclaim pumps"), t("≤ 1 100 м³/ч", "≤ 1,100 m³/h"))}
      {box(690, 406, W, t("Резервуар", "Process water"), t("4 000 м³ · блокировка", "4,000 m³ · interlock"))}
      {box(470, 406, W, t("Водозабор", "Water intake"), t("≤ 1 750 м³/ч", "≤ 1,750 m³/h"), "hot")}
      {box(30, 406, W, t("Подстанция", "Substation"), t("78 МВт · пик 58", "78 MW · peak 58"), "hot")}
    </svg>"""
    legend = (f'<div class="legend"><span><i class="ore"></i>{t("руда", "ore")}</span>'
              f'<span><i class="slurry"></i>{t("хвосты", "tailings")}</span>'
              f'<span><i class="water"></i>{t("вода", "water")}</span>'
              f'<span><i class="power"></i>{t("электроэнергия", "power")}</span>'
              f'<span><i class="hotk"></i>{t("общие лимиты", "shared limits")}</span></div>')
    return slide(head(t("Модель", "Mine model"), t(
        "Комплекс как одна система: руда, вода и энергия связаны",
        "The complex as one system: ore, water and power are linked")) + svg + legend +
        f'<p class="note">{t("23 двойника в Eclipse Ditto, пространство имён kz.limit. Связи — в атрибутах самих двойников: _parents (иерархия), ore_to, water_to, water_from, power_from (потоки).", "23 twins in Eclipse Ditto, namespace kz.limit. Links live in the twins’ own attributes: _parents (hierarchy), ore_to, water_to, water_from, power_from (flows).")}</p>')


def s_openegiz():
    return slide(head(t("Модель в OpenEgiz", "The model in OpenEgiz"), t(
        "23 двойника и 18 типов: состав, состояния, связи",
        "23 twins and 18 types: composition, states, links")) +
        f"""<div class="pair">
          <figure><img src="img/openegiz-twins.jpg" alt=""><figcaption>{t("OpenEgiz → Twins: комплекс и его 10 частей, у каждого двойника — картинка его объекта из 3D-сцены", "OpenEgiz → Twins: the complex and its 10 parts, each twin with a picture of its object from the 3D scene")}</figcaption></figure>
          <figure><img src="img/openegiz-types.jpg" alt=""><figcaption>{t("OpenEgiz → Types: состав типа «Обогатительная фабрика» — 2 линии измельчения, флотация, сгуститель, резервуар", "OpenEgiz → Types: the «Processing plant» type holds 2 grinding lines, flotation, a thickener and a tank")}</figcaption></figure>
        </div>
        <p class="note">{t("Типы — в пространстве имён kz.limit.type, у каждого двойника атрибут type. Состояния типа с единицами берутся из модели: тип совпадает с тем, что публикуется.", "Types live in the kz.limit.type namespace; every twin has a type attribute. A type’s states and units come from the model, so the type matches what is published.")}</p>""")


def s_physics():
    items = [
        (t("Твёрдость → энергия", "Hardness → energy"),
         "E = 1,35 · 10 · Wi · (1/√150 − 1/√100 000)" if LANG == "ru" else "E = 1.35 · 10 · Wi · (1/√150 − 1/√100,000)",
         t("Закон Бонда. Мельница упирается в мощность привода 22 МВт: твёрдая руда сама снижает производительность.",
           "Bond’s law. A mill is capped by its 22 MW drive: hard ore cuts throughput by itself.")),
        (t("Питание → вода", "Feed → water"),
         t("0,87 м³ воды на т руды", "0.87 m³ of water per t of ore"),
         t("Вода уходит с хвостами. Резервуар ниже 10 % — блокировка снижает питание фабрики. Высокоплотное сгущение экономит 0,2 м³/т за 0,4 кВт·ч/т.",
           "Water leaves with the tailings. Process tank below 10% — the interlock cuts plant feed. High-density thickening saves 0.2 m³/t for 0.4 kWh/t.")),
        (t("Нагрузка → САОН", "Load → shedding"),
         t("Σ нагрузок > лимита", "Σ loads > limit"),
         t("Экскаваторы, дробление, мельницы, флотация, насосы. Превышение лимита — автоматика отключает самую загруженную линию на 40 минут.",
           "Shovels, crushing, mills, flotation, pumps. Above the limit, load shedding trips the most loaded line for 40 minutes.")),
        (t("Склад развязывает", "Stockpile decouples"),
         t("карьер ≠ фабрика", "pit ≠ plant"),
         t("В пик фабрика снижает питание, карьер продолжает работать на склад. Пруд хвостохранилища — буфер воды на сутки и недели.",
           "In the peak the plant cuts feed while the pit keeps digging into the stockpile. The tailings pond is a water buffer for days and weeks.")),
    ]
    body = "".join(f'<div class="card"><h3>{esc(a)}</h3><div class="formula">{esc(f)}</div><p>{esc(c)}</p></div>' for a, f, c in items)
    return slide(head(t("Поведение", "Behaviour"), t(
        "Состояния связаны физикой, а не случайными числами",
        "States are linked by physics, not by random numbers")) + f'<div class="cards4">{body}</div>' +
        f'<p class="note">{t("Шаг симулятора — 2 минуты модели каждые 2 секунды (×60). Все параметры — в одном файле team/engine/params.py, общем для симулятора и оптимизатора.", "The simulator steps 2 model minutes every 2 seconds (×60). Every parameter is in one file, team/engine/params.py, shared by simulator and optimizer.")}</p>')


def s_platform():
    svg = f"""
    <svg viewBox="0 0 1440 400" class="diagram">
      <defs><marker id="a-p" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="#c9d2dc"/></marker></defs>
      <path d="M230,80 L330,80" class="fl plain" marker-end="url(#a-p)"/>
      <path d="M500,80 L600,80" class="fl plain" marker-end="url(#a-p)"/>
      <path d="M840,80 L920,80" class="fl plain" marker-end="url(#a-p)"/>
      <path d="M1150,80 L1200,80" class="fl plain" marker-end="url(#a-p)"/>
      <path d="M720,118 L720,180 L230,180 L230,250" class="fl plain" marker-end="url(#a-p)"/>
      <path d="M140,250 L140,118" class="fl plain" marker-end="url(#a-p)"/>
      <path d="M720,118 L720,250" class="fl plain" marker-end="url(#a-p)"/>
      <path d="M900,290 L840,180 L760,118" class="fl plain" marker-end="url(#a-p)"/>
      {box(50, 44, 180, "limit-simulator", t("физика комплекса", "complex physics"), "team")}
      {box(330, 44, 170, "Mosquitto", "MQTT telemetry/*")}
      {box(600, 44, 240, "Eclipse Ditto", t("23 двойника kz.limit:*", "23 twins kz.limit:*"), "core")}
      {box(920, 44, 230, "Telegraf → InfluxDB", t("история", "history"))}
      {box(1200, 44, 200, "Grafana", t("дашборды, Unity, Twins", "dashboards, Unity, Twins"))}
      {box(50, 250, 360, "limit-planner", t("LP на 24 ч → план в двойник planner", "24 h LP → plan into the planner twin"), "team")}
      {box(600, 250, 240, "limit-web (3D)", t("читает двойники из Ditto", "reads twins from Ditto"), "team")}
      {box(900, 290, 300, t("Кнопки сценариев", "Scenario buttons"), t("PUT в двойник control", "PUT into the control twin"))}
    </svg>"""
    pts = [
        t("Запись в двойники — только MQTT → Ditto, как у реального датчика. Оптимизатор отдаёт план тем же путём.",
          "Twins are written only MQTT → Ditto, like a real sensor. The optimizer publishes its plan the same way."),
        t("3D, Grafana и приложение Twins читают состояние из платформы. Сценарий «что если» — это запись в двойник control.",
          "3D, Grafana and the Twins app read state from the platform. A what-if scenario is a write into the control twin."),
        t("Всё стартует одной командой make up и проверяется make smoke. Внешних сервисов и ключей нет.",
          "Everything starts with one make up and is checked by make smoke. No external services or keys."),
    ]
    return slide(head(t("Платформа", "Platform"), t(
        "Построено на OpenEgiz, а не рядом с ним", "Built on OpenEgiz, not next to it")) + svg +
        '<ul class="pts">' + "".join(f"<li>{esc(p)}</li>" for p in pts) + "</ul>")


def s_optimizer():
    left = [
        t("Каждый час на 24 часа вперёд: добыча по забоям, питание мельниц по сортам со склада, режим сгустителя, свежая и оборотная вода",
          "For each of the next 24 hours: digging per face, mill feed per ore type from the stockpile, thickener mode, fresh and reclaimed water"),
        t("Цель — максимум меди в концентрате за сутки", "Goal — maximum copper in concentrate over the day"),
        t("Ограничения: мощность подстанции по часам (включая пик), водозабор, насосы, пруд, мельницы, дробилка, склад, горный план ±20 % по каждому сорту",
          "Limits: hourly substation power (incl. peak), intake, pumps, pond, mills, crusher, stockpile, mine plan ±20% per ore type"),
        t("SciPy / HiGHS, ~30 мс. Пересчёт каждые 15 минут модели, на смене часа и сразу при смене сценария",
          "SciPy / HiGHS, ~30 ms. Re-solved every 15 model minutes, on the hour and at once on any scenario change"),
    ]
    right = [
        (t("План", "Plan"), t("уставки уходят симулятору — модуль управляет рудником", "setpoints go to the simulator — the module runs the mine")),
        (t("По отделам", "By departments"), t("та же задача с правилами отделов: выигрыш плана в т меди", "same problem with department rules: the plan’s gain in t Cu")),
        (t("Без ограничений", "No limits"), t("во сколько тонн меди обходятся ограничения", "what the limits cost in tonnes of copper")),
        (t("Теневые цены", "Shadow prices"), t("+1 МВт в пик, +100 м³/ч воды, +100 т/ч мельниц — в тоннах меди", "+1 MW in peak, +100 m³/h water, +100 t/h mills — in tonnes of copper")),
    ]
    return slide(head(t("Модуль", "Module"), t(
        "Оптимизатор суточного плана: линейная программа на 24 часа",
        "Daily plan optimizer: a 24-hour linear program")) +
        '<div class="two"><ul class="pts">' + "".join(f"<li>{esc(p)}</li>" for p in left) + '</ul><div class="rows tight">' +
        "".join(f'<div class="row"><div class="lbl">{esc(a)}</div><div>{esc(b)}</div></div>' for a, b in right) + "</div></div>" +
        f'<p class="note">{t("Три решения за один пересчёт. Рекомендация диспетчеру строится по шаблонам из решения — без языковой модели и внешних API.", "Three solves per re-plan. The dispatcher’s advice is built from the solution by templates — no language model, no external API.")}</p>')


def s_viz():
    cap = [
        t("Потоки руды, воды и энергии анимированы и пропорциональны величинам из двойников",
          "Ore, water and power flows are animated in proportion to the twins’ values"),
        t("Узкие места по оценке оптимизатора — янтарная рамка; линия на ремонте — серая, отключённая САОН — красная",
          "Bottlenecks found by the optimizer get an amber frame; a line under repair is grey, a tripped one red"),
        t("Конусы склада по сортам, уровень резервуара, площадь пруда, время суток — из Ditto каждые 2 секунды",
          "Stockpile cones per ore type, tank level, pond area, time of day — from Ditto every 2 seconds"),
        t("Линии измельчения (МПСИ, шаровая мельница, привод, гидроциклоны) построены в коде, барабаны вращаются по питанию",
          "The grinding lines (SAG and ball mills, drives, hydrocyclones) are built in code; the drums turn with the feed"),
        t("Самосвалы (груженые вверх, порожние вниз), бульдозеры, поливочная машина — Poly Pizza: jeremy, Poly by Google, KolosStudios (CC BY 3.0); опоры ЛЭП и силосы — iPoly3D, MaverickFX (CC0); постройки — Kenney (CC0)",
          "Haul trucks (loaded up, empty down), dozers, water truck — Poly Pizza: jeremy, Poly by Google, KolosStudios (CC BY 3.0); towers and silos — iPoly3D, MaverickFX (CC0); buildings — Kenney (CC0)"),
    ]
    return slide(head(t("Визуализация", "Visualization"), t(
        "3D-вид комплекса: http://localhost:8100", "3D view of the complex: http://localhost:8100")) +
        '<div class="shot-wrap"><img class="shot" src="img/clean-3d.jpg" alt=""><ul class="pts side">' +
        "".join(f"<li>{esc(c)}</li>" for c in cap) + "</ul></div>")


def s_unity():
    cap = [
        t("Grafana → «Рудник под лимитом — Unity 3D»: та же сцена в Unity-панели OpenEgiz, сборка Unity 6 WebGL",
          "Grafana → «Рудник под лимитом — Unity 3D»: the same scene in the OpenEgiz Unity panel, a Unity 6 WebGL build"),
        t("Объекты названы по двойникам; на каждом обновлении дашборда панель отправляет каждому его значения из InfluxDB",
          "Objects are named after the twins; on every dashboard refresh the panel sends each one its values from InfluxDB"),
        t("Клик по объекту — карточка двойника, событие SelectTwin пишет его в переменную дашборда, таблица рядом показывает все значения",
          "Clicking an object shows its twin card; the SelectTwin event writes it into a dashboard variable, and the table next to it lists every value"),
        t("Сцена строится кодом из той же раскладки и с теми же моделями; make unity-on / make unity-off включают и выключают дашборд",
          "The scene is generated in code from the same layout and models; make unity-on / make unity-off switch the dashboard"),
    ]
    return slide(head(t("Визуализация в Grafana", "Visualization in Grafana"), t(
        "Сцена комплекса в Unity-панели", "The complex in the Unity panel")) +
        '<div class="shot-wrap"><img class="shot" src="img/grafana-unity.jpg" alt=""><ul class="pts side">' +
        "".join(f"<li>{esc(c)}</li>" for c in cap) + "</ul></div>")


def s_dispatcher():
    return slide(head(t("Для диспетчера", "For the dispatcher"), t(
        "Рекомендация, три плана и графики на 24 часа рядом со сценой",
        "Advice, three plans and 24-hour charts next to the scene")) +
        '<img class="shot full" src="img/peak-optimizer.jpg" alt="">' +
        f'<p class="note">{t("Маловодный год + вечерний пик, режим «План оптимизатора». Слева — ресурсы и сценарии, справа — рекомендация и план, внизу — журнал событий.", "Dry year + evening peak, «Optimizer plan» mode. Left: resources and scenarios; right: advice and plan; bottom: event log. The interface is in Russian.")}</p>')


def s_scenarios():
    rows = [
        ("dry_year", t("Маловодный год", "Dry year"), t("водозабор −30 %: 1 750 → 1 225 м³/ч", "intake −30%: 1,750 → 1,225 m³/h"),
         t("включает высокоплотное сгущение хвостов и держит питание", "switches thickening to high density and keeps the feed")),
        ("grid_peak", t("Вечерний пик", "Evening peak"), t("лимит 78 → 58 МВт, 18:00–22:00", "limit 78 → 58 MW, 18:00–22:00"),
         t("заранее снижает питание мельниц, карьер работает на склад", "cuts mill feed ahead of time, the pit digs into the stockpile")),
        ("mill2_repair", t("Мельница №2 на ремонте", "Mill 2 under repair"), t("одна линия измельчения из двух", "one grinding line of two"),
         t("пересчитывает план и шихту под одну линию", "re-plans the day and the blend for one line")),
        ("hard_ore", t("Твёрдая руда, забой 3", "Hard ore, face 3"), t("Wi 15,5 → 19,5 кВт·ч/т", "Wi 15.5 → 19.5 kWh/t"),
         t("снижает долю твёрдого сорта в пределах горного плана", "lowers the hard ore share within the mine plan")),
    ]
    body = "".join(f'<tr><td><b>{esc(n)}</b><br><code>{k}</code></td><td>{esc(c)}</td><td>{esc(r)}</td></tr>' for k, n, c, r in rows)
    return slide(head(t("Что если", "What-if"), t(
        "Четыре сценария: включаются и отменяются одной кнопкой",
        "Four scenarios: switched on and undone with one button")) +
        f'<table class="tbl big"><thead><tr><th>{t("Сценарий", "Scenario")}</th><th>{t("Что меняется", "What changes")}</th><th>{t("Что делает оптимизатор", "What the optimizer does")}</th></tr></thead><tbody>{body}</tbody></table>' +
        f'<p class="note">{t("Сценарии комбинируются. Кнопка пишет в двойник kz.limit:control; то же — curl PUT в Ditto. Переключатель «Каждый отдел сам» показывает, как комплекс работает без плана.", "Scenarios combine. A button writes into the kz.limit:control twin; the same works with a curl PUT to Ditto. The «Each department for itself» switch shows the complex running without the plan.")}</p>')


def s_results():
    top = 260.0
    groups = []
    for (name, a, b, gain, note) in RESULTS:
        ha, hb = a / top * 100, b / top * 100
        groups.append(f"""
          <div class="grp">
            <div class="delta">{'+' if gain >= 0 else ''}{f"{gain:.1f}".replace(".", "," if LANG == "ru" else ".")} %</div>
            <div class="bars">
              <div class="bar plan" style="height:{ha:.1f}%"><span>{a}</span></div>
              <div class="bar dept" style="height:{hb:.1f}%"><span>{b}</span></div>
            </div>
            <div class="gname">{esc(t(*name))}</div>
            <div class="gnote">{esc(t(*note))}</div>
          </div>""")
    legend = (f'<div class="legend"><span><i class="plan"></i>{t("План оптимизатора", "Optimizer plan")}</span>'
              f'<span><i class="dept"></i>{t("Каждый отдел сам", "Each department for itself")}</span></div>')
    return slide(head(t("Результат на модели", "Result on the model"), t(
        "Медь за сутки, т: выигрыш там, где ограничение",
        "Copper per day, t: the gain is where the limit is")) + legend +
        f'<div class="chart">{"".join(groups)}</div>' +
        f'<p class="note">{t("Сутки модели с 16:30, один и тот же симулятор; пересчёт — make evaluate (~10 с). Без ограничений план почти совпадает с работой по отделам: оптимизатору запрещено отходить от горного плана больше чем на ±20 %.", "One model day from 16:30, the same simulator; make evaluate recomputes it (~10 s). Without limits the plan nearly matches the departments: the optimizer may not leave the mine plan by more than ±20%.")}</p>')


def s_compare():
    return slide(head(t("Сравнение", "Side by side"), t(
        "Маловодный год + пик: план против «каждый отдел сам»",
        "Dry year + peak: plan vs «each department for itself»")) +
        f"""<div class="pair">
          <figure><img src="img/peak-optimizer.jpg" alt=""><figcaption>{t("План оптимизатора: питание снижено заранее, отключений нет", "Optimizer plan: feed cut in advance, no trips")}</figcaption>
            {stats([("8,35" if LANG == "ru" else "8.35", t("т Cu/ч в 19:32", "t Cu/h at 19:32")), ("56,4" if LANG == "ru" else "56.4", t("МВт при лимите 58", "MW, limit 58")), ("0", t("отключений САОН", "load-shedding trips")), ("237", t("т Cu за сутки", "t Cu per day"))], "plan")}</figure>
          <figure><img src="img/peak-departments.jpg" alt=""><figcaption>{t("Каждый отдел сам: САОН отключила линию измельчения №1", "Each department: load shedding tripped grinding line 1")}</figcaption>
            {stats([("5,03" if LANG == "ru" else "5.03", t("т Cu/ч в 20:00", "t Cu/h at 20:00")), ("1 " + t("из", "of") + " 2", t("линий в работе", "lines running")), ("6", t("отключений за сутки", "trips per day")), ("201", t("т Cu за сутки", "t Cu per day"))], "dept")}</figure>
        </div>""")


def stats(items, cls):
    return f'<div class="stats {cls}">' + "".join(
        f'<div><b>{esc(v)}</b><span>{esc(l)}</span></div>' for v, l in items) + "</div>"


def s_data():
    rows = [
        (t("Производительность", "Throughput"), t("2 × ~1 560 т/ч ≈ 25 млн т/год", "2 × ~1,560 t/h ≈ 25 Mt/y"), t("одна сульфидная фабрика Актогая (KAZ Minerals)", "one Aktogay sulphide plant (KAZ Minerals)")),
        (t("Содержание Cu", "Cu grade"), t("0,29 / 0,36 / 0,47 %", "0.29 / 0.36 / 0.47%"), t("Актогай: 0,32 % в ресурсах, 0,50 % в руде 2023 г.", "Aktogay: 0.32% in resources, 0.50% milled in 2023")),
        (t("Извлечение", "Recovery"), "85–89 %", t("Актогай, сульфидная фабрика: 88 %", "Aktogay sulphide plant: 88%")),
        (t("Индекс Бонда Wi", "Bond work index"), t("11,5 / 13,0 / 15,5 (19,5) кВт·ч/т", "11.5 / 13.0 / 15.5 (19.5) kWh/t"), t("справочник 911 Metallurgist: медная руда 12,7–14", "911 Metallurgist table: copper ore 12.7–14")),
        (t("Свежая вода", "Fresh water"), t("~0,52 м³/т", "~0.52 m³/t"), t("между Бозшаколем (0,43) и Актогаем (0,60), 2024", "between Bozshakol (0.43) and Aktogay (0.60), 2024")),
        (t("Вода в хвостах", "Water in tailings"), t("0,82 / 0,61 м³/т", "0.82 / 0.61 m³/t"), t("расчёт по плотности 55 / 62 % твёрдого", "computed from 55 / 62% solids")),
        (t("Лимиты", "Limits"), t("78 (пик 58) МВт · 1 750 м³/ч", "78 (peak 58) MW · 1,750 m³/h"), t("допущения команды, подобраны под удельные расходы", "Team assumptions, fitted to the unit consumptions")),
    ]
    body = "".join(f"<tr><td>{esc(a)}</td><td>{esc(b)}</td><td>{esc(c)}</td></tr>" for a, b, c in rows)
    return slide(head(t("Данные и допущения", "Data and assumptions"), t(
        "Данные синтетические, масштаб сверен с открытыми источниками",
        "Synthetic data, scale checked against open sources")) +
        f'<table class="tbl small"><thead><tr><th>{t("Параметр", "Parameter")}</th><th>{t("В модели", "In the model")}</th><th>{t("Источник", "Source")}</th></tr></thead><tbody>{body}</tbody></table>' +
        f'<p class="note">{t("Полная таблица со ссылками — SUBMISSION.md, раздел «Data and Assumptions». Конфиденциальных и персональных данных нет.", "Full table with links: SUBMISSION.md, «Data and Assumptions». No confidential or personal data.")}</p>')


def s_limits():
    lim = [
        t("Часовые балансы: нет рейсов самосвалов, буровзрывных работ, кинетики флотации", "Hourly balances: no truck cycles, drill and blast, flotation kinetics"),
        t("Извлечение по сорту постоянное; критерий — тонны меди, без цен и штрафов", "Recovery per ore type is constant; the goal is tonnes of copper, no prices or penalties"),
        t("Горизонт плана — 24 часа; сезонность испарения упрощена", "Plan horizon 24 hours; evaporation seasonality simplified"),
    ]
    nxt = [
        t("Деньги в критерии: цена меди, флокулянт, тариф на мощность", "Money in the goal: copper price, flocculant, capacity tariff"),
        t("Недельный горизонт и пруд как сезонный водный буфер", "A weekly horizon and the pond as a seasonal water buffer"),
        t("Подключение реальных данных АСУ ТП через тот же MQTT → Ditto", "Real plant data through the same MQTT → Ditto path"),
    ]
    return slide(head(t("Честно", "Honestly"), t("Ограничения и развитие", "Limitations and next steps")) +
        f'<div class="two"><div><h3>{t("Что упрощено", "What is simplified")}</h3><ul class="pts big">' + "".join(f"<li>{esc(x)}</li>" for x in lim) +
        f'</ul></div><div><h3>{t("Что дальше", "What is next")}</h3><ul class="pts big">' + "".join(f"<li>{esc(x)}</li>" for x in nxt) + "</ul></div></div>")


def s_team():
    rows = "".join(f'<div class="row"><div class="lbl mono">{esc(u)}</div><div>{esc(t(*r))}</div></div>' for u, r in TEAM)
    return slide(head(t("Команда", "Team"), t("team-101 и как запустить", "team-101 and how to run it")) +
        f'<div class="two"><div class="rows">{rows}</div><div>'
        f'<pre class="cmd">sudo apt-get update &amp;&amp; sudo apt-get install -y make\nmake up\nmake smoke</pre>'
        f'<div class="rows tight"><div class="row"><div class="lbl">3D</div><div>http://localhost:8100</div></div>'
        f'<div class="row"><div class="lbl">Grafana</div><div>http://localhost:3000 → {t("Рудник под лимитом", "Рудник под лимитом dashboard")}</div></div></div>'
        f'</div></div>')


SLIDES = [s_title, s_problem, s_concept, s_complex, s_openegiz, s_physics, s_platform, s_optimizer,
          s_viz, s_unity, s_dispatcher, s_scenarios, s_results, s_compare, s_data, s_limits, s_team]


def render(lang):
    global LANG
    LANG = lang
    with open(os.path.join(HERE, "slides.css"), encoding="utf-8") as f:
        css = f.read()
    body = "\n".join(s() for s in SLIDES)
    title = t("Рудник под лимитом", "Mine Under Limits")
    return f'<!doctype html><html lang="{lang}"><head><meta charset="utf-8"><title>{title}</title><style>{css}</style></head><body>{body}</body></html>'


def find_chrome():
    if os.environ.get("CHROME"):
        return os.environ["CHROME"]
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        if shutil.which(name):
            return shutil.which(name)
    sys.exit("Chrome/Chromium not found: set CHROME=/path/to/chrome")


def main():
    html_only = "--html" in sys.argv
    for lang, pdf in (("ru", "presentation.pdf"), ("en", "presentation.en.pdf")):
        page = os.path.join(HERE, f"slides.{lang}.html")
        with open(page, "w", encoding="utf-8") as f:
            f.write(render(lang))
        if html_only:
            continue
        out = os.path.join(ROOT, pdf)
        subprocess.run([find_chrome(), "--headless=new", "--no-sandbox", "--no-pdf-header-footer",
                        "--run-all-compositor-stages-before-draw", "--virtual-time-budget=5000",
                        f"--print-to-pdf={out}", "file://" + page], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        print(f"{pdf}: {os.path.getsize(out) // 1024} KiB")


if __name__ == "__main__":
    main()
