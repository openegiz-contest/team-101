#!/usr/bin/env python3
"""
Create or update the twins of the complex in Ditto (idempotent PUTs).

Each twin has `_parents` (the hierarchy shown in the OpenEgiz Twins UI) and
the flows it belongs to: `ore_to`, `water_to`, `power_from` name the twins
downstream, so the graph of the complex is in Ditto itself.
"""

import logging
import sys
import time
import urllib.error

import params as P
from platform_io import ditto

log = logging.getLogger("setup")


def twin(name, kind, title, parent=None, features=None, **attributes):
    attrs = {"name": title, "kind": kind, "_isType": False}
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


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    for name, body in definitions():
        for attempt in range(40):
            try:
                if name == "control":
                    # keep the scenario switches a running stand already has
                    try:
                        status, _ = ditto("GET", f"/things/{P.tid(name)}")
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
