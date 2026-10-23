#!/usr/bin/env python3
"""
Offline check of the «Result on the model» table in SUBMISSION.md.

Runs the same simulator (simulator.Complex) and the same planner (lp.solve,
planner.analyse) in one process, without the platform, for one model day from
SIM_START_HOUR, in both modes and under every scenario of the table. Prints
copper per day, load-shedding trips and water interlock hours.

    make evaluate                      # inside the engine image
    python3 team/engine/evaluate.py    # with paho-mqtt, numpy, scipy installed

The live Stand gives slightly different numbers: there the planner sees the
twins a tick later and the day may start at another hour.
"""

import logging
import os
import sys

import lp
import params as P
import planner
import simulator

DT_H = 2 / 60                       # one tick: 2 model minutes, as on the Stand
SEED = int(os.environ.get("SIM_SEED", "7"))

CASES = [
    ("Без ограничений", ()),
    ("Маловодный год", ("dry_year",)),
    ("Вечерний пик", ("grid_peak",)),
    ("Маловодный год + пик", ("dry_year", "grid_peak")),
    ("Мельница №2 на ремонте", ("mill2_repair",)),
    ("Твёрдая руда в забое №3", ("hard_ore",)),
]


def as_twins(snapshot):
    """The simulator's features in the shape Ditto returns them."""
    return {name: {"features": {k: {"properties": v} for k, v in feats.items()}}
            for name, feats in snapshot.items()}


def run_day(active, mode):
    sim = simulator.Complex(SEED)
    sim.flags.update({k: k in active for k in P.SCENARIOS})
    sim.mode = mode
    flags = dict(sim.flags)
    plan, last_key, last_hour = None, None, -1e9
    copper = interlock_h = 0.0
    shed = 0
    end = sim.hour + 24
    while sim.hour < end - 1e-9:
        if mode == "optimizer":
            twins = as_twins(sim.snapshot()) if sim.out else {}
            mills = tuple(sim.mill_state(m) for m in P.MILLS)
            key = (mills,)
            if (key != last_key or sim.hour - last_hour >= planner.RESOLVE_EVERY_H
                    or int(sim.hour) != int(last_hour)):
                twins["complex"] = {"features": {"sim_hour": {"properties": {"value": sim.hour}}}}
                state = planner.build_state(twins, flags)
                res = lp.solve(state)
                if res["ok"]:
                    plan = {**res["setpoint"], "next": res["next"], "until_hour": res["until_hour"]}
                last_key, last_hour = key, sim.hour
        shed_before = sim.today["shed"]
        sim.step(DT_H, plan)
        shed += sim.today["shed"] - shed_before if sim.today["shed"] >= shed_before else sim.today["shed"]
        copper += sim.out["copper"] * DT_H
        interlock_h += DT_H if sim.out["interlock"] else 0.0
    return copper, shed, interlock_h


def main():
    logging.disable(logging.INFO)
    print(f"Сутки модели с {simulator.clock(simulator.START_HOUR)}, seed {SEED}, шаг {DT_H * 60:.0f} мин\n")
    print("| Условия | План оптимизатора | Каждый отдел сам | Выигрыш |")
    print("|---|---|---|---|")
    for name, active in CASES:
        cu_o, shed_o, il_o = run_day(active, "optimizer")
        cu_d, shed_d, il_d = run_day(active, "departments")

        def note(shed, il):
            parts = []
            if shed:
                parts.append(f"{shed} откл. САОН")
            if il >= 0.05:
                parts.append(f"блокировка по воде {il:.1f} ч")
            return (", " + ", ".join(parts)) if parts else ""

        gain = (cu_o - cu_d) / cu_d * 100
        print(f"| {name} | {cu_o:.0f} т Cu{note(shed_o, il_o)} | {cu_d:.0f} т Cu{note(shed_d, il_d)} | {gain:+.1f} % |")
    return 0


if __name__ == "__main__":
    sys.exit(main())
