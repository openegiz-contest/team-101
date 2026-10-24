#!/usr/bin/env python3
"""
Create or update the twins of the complex in Ditto (idempotent PUTs).

Each twin has `_parents` (the hierarchy shown in the OpenEgiz Twins UI) and
the flows it belongs to: `ore_to`, `water_to`, `power_from` name the twins
downstream, so the graph of the complex is in Ditto itself.

Each twin also has `type`, one of the OpenEgiz types in the namespace
kz.limit.type (the Types UI): what the object is, which states it has with
their units, and what it consists of (`_parents` of a type with a count, so
the plant type holds two grinding lines and the pit type three faces).
"""

import logging
import os
import sys
import time
import urllib.error

import lp
import params as P
import planner
import simulator
from platform_io import ditto

log = logging.getLogger("setup")

# Pictures for the OpenEgiz Twins app, cut from the 3D page and served by it
# (team/web/img/). The browser loads them, so this is the address it sees.
WEB_URL = os.environ.get("WEB_URL", "http://localhost:8100").rstrip("/")

# A namespace of their own keeps the types out of the dashboards and the
# Unity scene, which take every thing matching ^kz.limit: from InfluxDB.
TYPE_NS = "kz.limit.type"
TYPES = {   # kind -> name and description of the type
    "complex": ("Горно-обогатительный комплекс", "Карьер, дробление, фабрика, хвостовое хозяйство, водо- и электроснабжение под общими лимитами"),
    "control": ("Сценарии «что если»", "Переключатели сценариев и режим планирования: оптимизатор или каждый отдел сам"),
    "module": ("Модуль-оптимизатор", "Суточный план на 24 часа (линейная программа), узкие места, теневые цены лимитов, рекомендация диспетчеру"),
    "pit": ("Карьер", "Открытая разработка: забои и экскаваторы, суммарная добыча и мощность"),
    "face": ("Забой", "Участок одного сорта руды: содержание меди, крепость (Bond Wi), извлечение, добыча"),
    "shovel": ("Карьерный экскаватор", "Электрический экскаватор забоя: производительность и потребляемая мощность"),
    "crusher": ("Дробилка крупного дробления", "Конусная дробилка: производительность, загрузка, мощность"),
    "conveyor": ("Магистральный конвейер", "Транспорт дроблёной руды на склад"),
    "stockpile": ("Склад дроблёной руды", "Буфер между карьером и фабрикой: запас по трём сортам и заполнение"),
    "plant": ("Обогатительная фабрика", "Измельчение, флотация, сгущение хвостов и оборотная вода"),
    "mill": ("Линия измельчения", "МПСИ + шаровая мельница: питание, мощность, загрузка, удельная энергия; ремонт и отключение САОН"),
    "flotation": ("Флотация", "Извлечение меди и выпуск концентрата"),
    "thickener": ("Сгуститель хвостов", "Режим (обычный или высокоплотный), содержание твёрдого, вода с хвостами"),
    "tank": ("Резервуар оборотной воды", "Уровень и расход воды фабрики; блокировка при опустошении"),
    "water-intake": ("Водозабор свежей воды", "Забор из канала в пределах разрешённого лимита"),
    "tailings": ("Хвостохранилище", "Объём пруда, запас оборотной воды, потери на испарение и фильтрацию"),
    "pump-station": ("Насосная оборотной воды", "Возврат осветлённой воды из пруда на фабрику"),
    "substation": ("Понизительная подстанция", "Нагрузка комплекса и лимит мощности энергосистемы, отключения САОН"),
}


def twin(name, kind, title, parent=None, features=None, **attributes):
    attrs = {"name": title, "kind": kind, "type": f"{TYPE_NS}:{kind}", "_isType": False,
             "image": f"{WEB_URL}/img/{name}.jpg"}
    if parent:
        attrs["_parents"] = P.tid(parent)
    attrs.update(attributes)
    return name, {
        "policyId": "default:basic_policy",
        "attributes": attrs,
        "features": {f: {"properties": props} for f, props in (features or {}).items()},
    }


def definitions():
    sub = "substation"
    yield twin("complex", "complex", "Медный ГОК «Сары-Тау» (вымышленный)",
               description="Карьер, дробление, фабрика, хвостохранилище, водозабор и подстанция")
    yield twin("control", "control", "Сценарии «что если» и режим планирования", "complex",
               features={**{k: {"active": False, "title": t} for k, t in P.SCENARIOS.items()},
                         "mode": {"value": "optimizer"}})
    yield twin("planner", "module", "Модуль: оптимизатор суточного плана", "complex")
    yield twin("pit", "pit", "Карьер", "complex", power_from=P.tid(sub))
    for i, (face, f) in enumerate(P.FACES.items(), 1):
        yield twin(face, "face", f["name"], "pit", grade_pct=f["grade"], bond_wi=f["wi"],
                   recovery_pct=f["recovery"], plan_share=P.PIT_PLAN_SHARE[face])
        yield twin(f"shovel-{i}", "shovel", f"Экскаватор ЭКГ-{i} (электрический)", "pit",
                   face=P.tid(face), rated_tph=f["shovel_tph"], ore_to=P.tid("crusher"), power_from=P.tid(sub))
    yield twin("crusher", "crusher", "Конусная дробилка ККД", "complex", rated_tph=P.CRUSHER_TPH,
               ore_to=P.tid("conveyor"), power_from=P.tid(sub))
    yield twin("conveyor", "conveyor", "Магистральный конвейер, 3 км", "complex", rated_tph=P.CRUSHER_TPH,
               ore_to=P.tid("stockpile"), power_from=P.tid(sub))
    yield twin("stockpile", "stockpile", "Склад крупнодроблёной руды (3 штабеля по сортам)", "complex",
               capacity_t=P.STOCKPILE_CAP_T, ore_to=",".join(P.tid(m) for m in P.MILLS))
    yield twin("plant", "plant", "Обогатительная фабрика", "complex", power_from=P.tid(sub))
    for i, m in enumerate(P.MILLS, 1):
        yield twin(m, "mill", f"Линия измельчения №{i} (МПСИ + шаровая)", "plant", installed_kw=P.MILL_KW,
                   max_tph=P.MILL_MAX_TPH, ore_to=P.tid("flotation"), water_from=P.tid("process-water"),
                   power_from=P.tid(sub))
    yield twin("flotation", "flotation", "Флотация", "plant", concentrate_grade_pct=P.CONC_GRADE,
               ore_to=P.tid("thickener"), water_from=P.tid("process-water"), power_from=P.tid(sub))
    yield twin("thickener", "thickener", "Сгуститель хвостов", "plant", ore_to=P.tid("tailings"),
               water_to=P.tid("tailings"), power_from=P.tid(sub))
    yield twin("process-water", "tank", "Резервуар оборотной воды фабрики", "plant", volume_m3=P.PROCESS_TANK_M3,
               water_to=",".join(P.tid(x) for x in (*P.MILLS, "flotation")))
    yield twin("water-intake", "water-intake", "Водозабор и водовод с канала", "complex",
               permit_m3h=P.FRESH_LIMIT_M3H, water_to=P.tid("process-water"), power_from=P.tid(sub))
    yield twin("tailings", "tailings", "Хвостохранилище", "complex", water_to=P.tid("reclaim"),
               min_pond_m3=P.POND_MIN_M3)
    yield twin("reclaim", "pump-station", "Насосная оборотной воды (плавучая)", "tailings",
               capacity_m3h=P.RECLAIM_CAP_M3H, water_to=P.tid("process-water"), power_from=P.tid(sub))
    yield twin(sub, "substation", "Главная понизительная подстанция 220/10 кВ", "complex",
               contracted_mw=P.GRID_LIMIT_MW)


def feature_templates():
    """The states every twin has, with units, as the model publishes them:
    one step of the simulator and one plan of the optimizer."""
    sim = simulator.Complex(0)
    sim.step(2 / 60, None)
    snap = sim.snapshot()
    twins = {n: {"features": {k: {"properties": v} for k, v in f.items()}} for n, f in snap.items()}
    flags = {k: False for k in P.SCENARIOS}
    state = planner.build_state(twins, flags)
    plan, base = lp.solve(state), lp.solve(state, baseline=True)
    ref = lp.solve(planner.build_state(twins, flags, ignore_scenarios=True))
    if plan["ok"] and base["ok"] and ref["ok"]:
        snap["planner"] = planner.analyse(state, plan, base, ref, flags, "optimizer")
    return snap


def types(twins):
    """The OpenEgiz types of the complex, from its twins."""
    try:
        published = feature_templates()
    except Exception as exc:                     # the types are still made, without states
        log.warning("feature templates not computed: %s", exc)
        published = {}
    kind = {name: body["attributes"]["kind"] for name, body in twins}
    count = {}
    for name, body in twins:
        parent = body["attributes"].get("_parents", "").split(":")[-1]
        if parent:
            key = (kind[name], kind[parent])
            count[key] = count.get(key, 0) + 1
    # every parent kind has one twin, so the count is how many it holds
    first = {}
    for name, body in twins:
        first.setdefault(kind[name], (name, body))
    for k, (name, body) in first.items():
        title, description = TYPES[k]
        feats = published.get(name) or {f: f_["properties"] for f, f_ in body["features"].items()}
        attrs = {"name": title, "description": description, "_isType": True, "image": body["attributes"]["image"]}
        parents = {f"{TYPE_NS}:{pk}": n for (ck, pk), n in count.items() if ck == k}
        if parents:
            attrs["_parents"] = parents
        yield f"{TYPE_NS}:{k}", {
            "policyId": "default:basic_policy",
            "attributes": attrs,
            "features": {f: {"properties": {"unit": p["unit"]} if p.get("unit") else {}} for f, p in feats.items()},
        }


def put(thing_id, body):
    for attempt in range(40):
        try:
            status, _ = ditto("PUT", f"/things/{thing_id}", body)
            log.info("%s  %s", "created" if status == 201 else "updated", thing_id)
            return True
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            if attempt == 39:
                log.error("FAILED %s: %s", thing_id, exc)
                return False
            time.sleep(3)


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    twins = list(definitions())
    for type_id, body in types(twins):
        if not put(type_id, body):
            return 1
    for name, body in twins:
        for attempt in range(40):
            try:
                if name == "control":
                    # keep the scenario switches a running stand already has
                    try:
                        status, _ = ditto("GET", f"/things/{P.tid(name)}")
                        for a in ("image", "type"):
                            ditto("PUT", f"/things/{P.tid(name)}/attributes/{a}", body["attributes"][a])
                        log.info("kept     %s", P.tid(name))
                        break
                    except urllib.error.HTTPError as exc:
                        if exc.code != 404:
                            raise
                status, _ = ditto("PUT", f"/things/{P.tid(name)}", body)
                log.info("%s  %s", "created" if status == 201 else "updated", P.tid(name))
                break
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                if attempt == 39:
                    log.error("FAILED %s: %s", name, exc)
                    return 1
                time.sleep(3)
    return 0


if __name__ == "__main__":
    sys.exit(main())
