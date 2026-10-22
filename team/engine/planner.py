#!/usr/bin/env python3
"""
Module «Оптимизатор суточного плана».

Reads the state of the complex from its twins in Ditto, solves the day plan
(lp.py) and publishes it to the planner twin through MQTT -> Ditto:

  * setpoints for the current hour, which the simulator follows in the
    «optimizer» mode;
  * the 24-hour schedule, its copper, and the copper of two references:
    the proportional cut by departments, and the same day without the
    active scenarios — what the limits cost;
  * shadow prices: what one more MW or 100 m³/h would be worth in copper;
  * the bottleneck (twins to highlight) and the advice text for the
    dispatcher, from templates — no language model, nothing external.
"""

import json
import logging
import math
import os
import signal
import sys
import time

import lp
import params as P
from platform_io import connect_mqtt, get_things, prop, publish_features, wait_for_ditto

log = logging.getLogger("planner")

READ = ["complex", "control", "stockpile", "tailings", *P.MILLS]
RESOLVE_EVERY_H = 0.25


def num(x, nd=0):
    if abs(x) < 0.5 * 10 ** -nd:
        x = 0.0
    s = f"{x:,.{nd}f}".replace(",", " ").replace(".", ",")
    return s.replace("-", "−")


def hour_ranges(hours, first=None):
    """[18, 19, 20, 21] -> '18:00–22:00'; ranges that start after the plan
    has passed midnight and before its first hour are marked «завтра»."""
    if not hours:
        return ""
    if len(hours) >= lp.H:
        return "весь день"
    first = hours[0] if first is None else first
    out, start, prev = [], hours[0], hours[0]
    for h in hours[1:] + [None]:
        if h is not None and h == (prev + 1) % 24:
            prev = h
            continue
        tomorrow = "завтра " if start < first and start != first else ""
        out.append(f"{tomorrow}{start:02d}:00–{(prev + 1) % 24:02d}:00")
        if h is not None:
            start = prev = h
    return ", ".join(out)


def build_state(twins, flags, ignore_scenarios=False):
    hour = prop(twins.get("complex"), "sim_hour", default=float(os.environ.get("SIM_START_HOUR", "16.5")))
    f = {k: (False if ignore_scenarios else v) for k, v in flags.items()}
    lines = []
    trip_h = {m: (0.0 if ignore_scenarios else (prop(twins.get(m), "trip_left", default=0) or 0) / 60.0)
              for m in P.MILLS}
    for t in range(lp.H):
        n = 0
        for m in P.MILLS:
            if m == "mill-2" and f["mill2_repair"]:
                continue
            if t < math.ceil(trip_h[m]):
                continue
            n += 1
        lines.append(n)
    wi = {face: P.FACES[face]["wi"] for face in P.FACE_IDS}
    if f["hard_ore"]:
        wi["face-3"] = P.HARD_ORE_WI
    stock = {face: float(prop(twins.get("stockpile"), f"section_{i}", default=P.STOCKPILE_START_T[face]))
             for i, face in enumerate(P.FACE_IDS, 1)}
    return {
        "hour": hour,
        "wi": wi,
        "lines": lines,
        "power_mw": [P.default_power_limit_mw((int(hour) + t) % 24, f["grid_peak"]) for t in range(lp.H)],
        "fresh_m3h": [P.FRESH_LIMIT_M3H * (P.DRY_YEAR_FACTOR if f["dry_year"] else 1.0)] * lp.H,
        "stock": stock,
        "pond_m3": float(prop(twins.get("tailings"), "pond_volume", default=P.POND_START_M3)),
    }


def analyse(state, plan, base, ref, flags, mode):
    sched = plan["schedule"]
    sh = plan["shadow"]
    hours = sched["hour"]
    # A limit is a bottleneck when relaxing it would add real copper, not
    # just move the tiny tie-breaking weights of the objective. Thresholds:
    # 1 MW for an hour ~ 0.01 t Cu, 100 m³/h or 100 t/h for an hour ~ 0.01 t.
    tol = {"power": 1e-5, "water": 1e-4, "mill": 1e-4, "crusher": 2e-3}

    def binding(series, kind):
        return [hours[t] for t, d in enumerate(series) if d > tol[kind]]

    mill_series = [a + b * P.grind_kwh_t(13.0) for a, b in zip(sh["mill_tph"], sh["mill_kw"])]
    power_h = binding(sh["power_kw"], "power")
    fresh_h = binding(sh["fresh_m3h"], "water")
    mill_h = binding(mill_series, "mill")
    reclaim_h = binding(sh["reclaim_m3h"], "water")
    crusher_h = binding(sh["crusher"], "crusher")

    bottlenecks, twins_now = [], []
    if power_h:
        bottlenecks.append(f"мощность подстанции ({hour_ranges(power_h, hours[0])})")
        if sh["power_kw"][0] > tol["power"]:
            twins_now.append("substation")
    # the intake used to its permit is worth naming even when thickening
    # makes the last m³ cheap
    fresh_full = [hours[t] for t in range(lp.H) if sched["fresh"][t] >= 0.99 * state["fresh_m3h"][t]]
    if fresh_h or fresh_full:
        hrs = sorted(set(fresh_h) | set(fresh_full), key=hours.index)
        bottlenecks.append(f"лимит водозабора ({hour_ranges(hrs, hours[0])})")
        if sh["fresh_m3h"][0] > tol["water"] or sched["fresh"][0] >= 0.99 * state["fresh_m3h"][0]:
            twins_now.append("water-intake")
    if reclaim_h:
        bottlenecks.append(f"насосы оборотной воды ({hour_ranges(reclaim_h, hours[0])})")
        if sh["reclaim_m3h"][0] > tol["water"]:
            twins_now += ["reclaim", "tailings"]
    if mill_h:
        bottlenecks.append(f"мельницы ({hour_ranges(mill_h, hours[0])})")
        if mill_series[0] > tol["mill"]:
            twins_now += [m for m in P.MILLS if state["lines"][0] == 2 or m == "mill-1"]
    if crusher_h:
        bottlenecks.append(f"дробилка ({hour_ranges(crusher_h, hours[0])})")
        if sh["crusher"][0] > tol["crusher"]:
            twins_now.append("crusher")

    peak_hours = [t for t in range(lp.H) if state["power_mw"][t] < P.GRID_LIMIT_MW]
    if peak_hours:
        value_power = sum(sh["power_kw"][t] for t in peak_hours) * 1000
        power_scope = "в пиковые часы"
    else:
        value_power = sum(sh["power_kw"]) * 1000
        power_scope = "круглосуточно"
    value_water = sum(sh["fresh_m3h"]) * 100
    value_mill = sum(mill_series) * 100

    sp = plan["setpoint"]
    gain = plan["copper_day"] - base["copper_day"]
    gain_pct = gain / base["copper_day"] * 100 if base["copper_day"] > 0 else 0.0
    cost = ref["copper_day"] - plan["copper_day"]
    lines0 = state["lines"][0]
    ore0 = sum(sp["feed"].values())

    advice = []
    if bottlenecks:
        advice.append("Узкие места: " + "; ".join(bottlenecks) + ".")
    else:
        advice.append("Узких мест нет: комплекс может работать на полную мощность.")
    advice.append("Карьер сейчас: " + ", ".join(
        f"забой {i} — {num(sp['dig'][f])} т/ч" for i, f in enumerate(P.FACE_IDS, 1)) + ".")
    if lines0:
        advice.append(f"Фабрика: {num(ore0)} т/ч на {lines0} лин. "
                      f"(по {num(ore0 / lines0)} т/ч), смесь со склада: " + ", ".join(
                          f"сорт {i} — {num(sp['feed'][f] / ore0 * 100 if ore0 else 0)} %" for i, f in enumerate(P.FACE_IDS, 1)) + ".")
    else:
        advice.append("Фабрика стоит: ни одна линия измельчения не работает.")
    if sp["thick"] > 1:
        advice.append(f"Сгуститель хвостов: высокоплотный режим ({P.TAILS_SOLIDS_HIGH * 100:.0f} % твёрдого) "
                      f"на {num(sp['thick'])} т/ч — экономит {num(sp['thick'] * P.THICK_SAVING_M3_T)} м³/ч воды.")
    advice.append(f"Вода: возврат из хвостохранилища {num(sp['reclaim'])} м³/ч, свежая {num(sp['fresh'])} м³/ч "
                  f"из {num(state['fresh_m3h'][0])}.")
    if peak_hours:
        low = min(sched["ore"][t] for t in peak_hours)
        stock_peak_end = sched["stock"][peak_hours[-1]]
        advice.append(f"Пик {hour_ranges([hours[t] for t in peak_hours], hours[0])}: загрузка фабрики снижается до "
                      f"{num(low)} т/ч, карьер продолжает работу на склад "
                      f"(на складе к концу пика {num(stock_peak_end / 1000, 1)} тыс. т).")
    advice.append(f"План на 24 ч: {num(plan['copper_day'], 1)} т меди. Пропорциональное сокращение по отделам: "
                  f"{num(base['copper_day'], 1)} т. Выигрыш плана: {'+' if gain >= 0 else ''}{num(gain, 1)} т "
                  f"({'+' if gain >= 0 else ''}{num(gain_pct, 1)} %).")
    if cost > 0.05:
        advice.append(f"Действующие ограничения стоят {num(cost, 1)} т меди за сутки.")
    worth = []
    if value_power > 0.005:
        worth.append(f"+1 МВт {power_scope} = +{num(value_power, 2)} т меди")
    if value_water > 0.005:
        worth.append(f"+100 м³/ч свежей воды = +{num(value_water, 2)} т меди за сутки")
    if value_mill > 0.005:
        worth.append(f"+100 т/ч мощности мельниц = +{num(value_mill, 2)} т меди за сутки")
    if worth:
        advice.append("Цена ресурса: " + "; ".join(worth) + ".")
    if mode != "optimizer":
        advice.append("Режим «по отделам»: план не применяется, отделы работают каждый на свой максимум.")

    schedule = {k: [round(v, 1) for v in vals] if k != "hour" else vals for k, vals in sched.items()}
    schedule["baseline_ore"] = [round(v, 1) for v in base["schedule"]["ore"]]
    schedule["baseline_copper"] = [round(v, 3) for v in base["schedule"]["copper"]]
    schedule["copper"] = [round(v, 3) for v in sched["copper"]]

    def v(value, unit=None):
        d = {"value": value}
        if unit:
            d["unit"] = unit
        return d

    def rounded(d):
        return {k: (rounded(val) if isinstance(val, dict) else round(val, 3 if k == "until_hour" else 1))
                for k, val in d.items()}

    setpoint = rounded({**sp, "next": plan["next"], "until_hour": plan["until_hour"]})
    return {
        "status": v("optimal"),
        "mode_applied": v(mode == "optimizer"),
        "solved_at": v(prop_clock(state["hour"])),
        "copper_plan_day": v(round(plan["copper_day"], 2), "t"),
        "copper_baseline_day": v(round(base["copper_day"], 2), "t"),
        "copper_reference_day": v(round(ref["copper_day"], 2), "t"),
        "gain": v(round(gain, 2), "t"),
        "gain_pct": v(round(gain_pct, 2), "%"),
        "limits_cost": v(round(max(cost, 0.0), 2), "t"),
        "value_power_mw": v(round(value_power, 3), "t Cu per MW"),
        "value_power_scope": v(power_scope),
        "value_water_100m3h": v(round(value_water, 3), "t Cu per 100 m3/h"),
        "value_mill_100tph": v(round(value_mill, 3), "t Cu per 100 t/h"),
        "bottleneck": v("; ".join(bottlenecks) or "нет"),
        "bottleneck_twins": v(",".join(dict.fromkeys(twins_now))),
        "advice": v("\n".join(advice)),
        "plan_ore": v(round(ore0, 1), "t/h"),
        "plan_dig": v(round(sum(sp["dig"].values()), 1), "t/h"),
        "plan_thick": v(round(sp["thick"], 1), "t/h"),
        "plan_fresh": v(round(sp["fresh"], 1), "m3/h"),
        "plan_reclaim": v(round(sp["reclaim"], 1), "m3/h"),
        "setpoint": v(setpoint),
        "schedule": v(json.dumps(schedule, separators=(",", ":"))),
    }


def prop_clock(hour):
    h = int(hour) % 24
    return f"{h:02d}:{int((hour - int(hour)) * 60):02d}"


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    wait_for_ditto(READ)
    client = connect_mqtt("limit-planner")
    stop = False

    def on_signal(*_):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    last_key, last_hour = None, -1e9
    while not stop:
        try:
            twins = get_things(READ)
        except Exception as exc:
            log.warning("reading twins failed: %s", exc)
            time.sleep(2)
            continue
        control = twins.get("control")
        flags = {k: bool(prop(control, k, "active", False)) for k in P.SCENARIOS}
        mode = prop(control, "mode", default="optimizer")
        mills = tuple(prop(twins.get(m), "state", default="running") for m in P.MILLS)
        hour = prop(twins.get("complex"), "sim_hour", default=0.0) or 0.0
        key = (tuple(sorted(flags.items())), mode, mills)
        if (key != last_key or hour - last_hour >= RESOLVE_EVERY_H or hour < last_hour
                or int(hour) != int(last_hour)):
            state = build_state(twins, flags)
            started = time.monotonic()
            plan = lp.solve(state)
            base = lp.solve(state, baseline=True)
            ref = lp.solve(build_state(twins, flags, ignore_scenarios=True))
            if plan["ok"] and base["ok"] and ref["ok"]:
                features = analyse(state, plan, base, ref, flags, mode)
                log.info("%s solved in %.0f ms: %.1f t Cu/day (baseline %.1f, no limits %.1f) | %s",
                         prop_clock(state["hour"]), (time.monotonic() - started) * 1000, plan["copper_day"],
                         base["copper_day"], ref["copper_day"], features["bottleneck"]["value"])
            else:
                msg = next(r.get("message") for r in (plan, base, ref) if not r["ok"])
                log.error("no plan: %s", msg)
                features = {"status": {"value": "infeasible"}, "advice": {"value": f"План не найден: {msg}"}}
            publish_features(client, "planner", features)
            last_key, last_hour = key, hour
        time.sleep(2)
    client.loop_stop()
    client.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(main())
