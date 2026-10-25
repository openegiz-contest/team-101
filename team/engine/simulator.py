#!/usr/bin/env python3
"""
Simulator of the «Рудник под лимитом» complex.

Every tick it advances the physics of the whole chain and publishes the state
of every twin to MQTT as Ditto protocol commands (MQTT -> Ditto -> Telegraf
-> InfluxDB, like any device). It reads two twins back from Ditto:

  * control — the what-if scenarios and the planning mode the dispatcher set;
  * planner — the setpoints of the optimizer's plan for the current hour.

In the «optimizer» mode the complex follows the planner's setpoints. In the
«departments» mode every department runs its own part flat out, as it does
today, and only the interlocks react: the plant cuts feed when the process
water tank runs dry, and the grid's load shedding trips a mill line when the
substation is over its limit.
"""

import json
import logging
import os
import random
import signal
import sys
import time

import params as P
from platform_io import connect_mqtt, get_things, prop, publish_features, wait_for_ditto

log = logging.getLogger("sim")

START_HOUR = float(os.environ.get("SIM_START_HOUR", "16.5"))
NAMES_TO_READ = ["control", "planner"]


def clock(hour):
    h = int(hour) % 24
    return f"{h:02d}:{int((hour - int(hour)) * 60):02d}"


class Complex:
    def __init__(self, seed):
        self.rng = random.Random(seed)
        self.hour = START_HOUR          # hours since day 0, 00:00
        self.stock = dict(P.STOCKPILE_START_T)
        self.tank = P.PROCESS_TANK_M3 * P.PROCESS_TANK_START
        self.pond = P.POND_START_M3
        self.mill_trip_until = {m: -1.0 for m in P.MILLS}
        self.today = {"copper": 0.0, "ore": 0.0, "fresh": 0.0, "shed": 0, "interlock_h": 0.0,
                      **{f"dug_{f}": 0.0 for f in P.FACE_IDS}}
        self.events = []
        self.flags = {k: False for k in P.SCENARIOS}
        self.mode = "optimizer"
        self.out = {}
        self.noise = {f: 1.0 for f in P.FACE_IDS}

    # -- helpers -------------------------------------------------------------
    def event(self, text):
        line = f"{clock(self.hour)} {text}"
        log.info("event: %s", line)
        self.events = ([line] + self.events)[:12]

    def wi(self, face):
        return P.HARD_ORE_WI if face == "face-3" and self.flags["hard_ore"] else P.FACES[face]["wi"]

    def mill_state(self, m):
        if m == "mill-2" and self.flags["mill2_repair"]:
            return "repair"
        if self.hour < self.mill_trip_until[m]:
            return "tripped"
        return "running"

    def apply_control(self, control):
        for k in P.SCENARIOS:
            on = bool(prop(control, k, "active", False))
            if on != self.flags[k]:
                self.flags[k] = on
                self.event(("Сценарий включён: " if on else "Сценарий отменён: ") + P.SCENARIOS[k])
        mode = prop(control, "mode", default="optimizer")
        mode = mode if mode in ("optimizer", "departments") else "optimizer"
        if mode != self.mode:
            self.mode = mode
            self.event("Режим: " + ("план оптимизатора" if mode == "optimizer" else "каждый отдел по своему плану"))

    # -- one tick --------------------------------------------------------------
    def step(self, dt_h, plan):
        rng = self.rng
        hour_of_day = self.hour % 24
        fresh_limit = P.FRESH_LIMIT_M3H * (P.DRY_YEAR_FACTOR if self.flags["dry_year"] else 1.0)
        power_limit = P.default_power_limit_mw(hour_of_day, self.flags["grid_peak"])
        running = [m for m in P.MILLS if self.mill_state(m) == "running"]
        e = {f: P.grind_kwh_t(self.wi(f)) for f in P.FACE_IDS}
        for f in P.FACE_IDS:   # slow wander of shovel performance
            self.noise[f] = min(1.05, max(0.92, self.noise[f] + rng.gauss(0, 0.01)))

        use_plan = self.mode == "optimizer" and plan is not None
        if use_plan and self.hour >= plan.get("until_hour", 1e9) - 1e-6 and isinstance(plan.get("next"), dict):
            plan = plan["next"]
        if use_plan:
            dig = {f: plan["dig"].get(f, 0.0) for f in P.FACE_IDS}
            feed = {f: plan["feed"].get(f, 0.0) for f in P.FACE_IDS}
            thick = plan["thick"]
            reclaim_sp = plan["reclaim"]
            # the plan assumed the lines it knew about; a line it did not know is down
            planned_lines = plan.get("lines", len(running)) or 1
            if len(running) < planned_lines:
                k = len(running) / planned_lines
                feed = {f: v * k for f, v in feed.items()}
        else:
            dig = {f: P.PIT_PLAN_SHARE[f] * P.PIT_PLAN_TPH for f in P.FACE_IDS}
            blend_e = sum(P.PIT_PLAN_SHARE[f] * e[f] for f in P.FACE_IDS)
            total = len(running) * min(P.MILL_MAX_TPH, P.MILL_KW / blend_e)
            feed = {f: P.PIT_PLAN_SHARE[f] * total for f in P.FACE_IDS}
            thick = 0.0
            reclaim_sp = P.RECLAIM_CAP_M3H

        # pit -> crusher -> conveyor -> stockpile sections
        dig = {f: min(v, P.FACES[f]["shovel_tph"]) * self.noise[f] for f, v in dig.items()}
        total_dig = sum(dig.values())
        if total_dig > P.CRUSHER_TPH:
            dig = {f: v * P.CRUSHER_TPH / total_dig for f, v in dig.items()}
        room = P.STOCKPILE_CAP_T - sum(self.stock.values())
        if sum(dig.values()) * dt_h > room:
            k = max(room, 0.0) / (sum(dig.values()) * dt_h)
            dig = {f: v * k for f, v in dig.items()}
        # stockpile -> mills, limited by what each section holds
        feed = {f: min(v, (self.stock[f] + dig[f] * dt_h) / dt_h) for f, v in feed.items()}
        total_feed = sum(feed.values())
        if not running:
            feed = {f: 0.0 for f in feed}
            total_feed = 0.0
        lines = max(len(running), 1)
        if total_feed > 0:
            e_blend = sum(feed[f] * e[f] for f in feed) / total_feed
            cap = lines * min(P.MILL_MAX_TPH, P.MILL_KW / e_blend)
            if total_feed > cap:
                feed = {f: v * cap / total_feed for f, v in feed.items()}
                total_feed = cap
        else:
            e_blend = sum(P.PIT_PLAN_SHARE[f] * e[f] for f in P.FACE_IDS)
        thick = min(thick, total_feed)

        # water: the plant draws make-up from the tank; reclaim and fresh refill it
        demand = P.WATER_NET_M3_T * total_feed - P.THICK_SAVING_M3_T * thick
        reclaim = min(reclaim_sp, P.RECLAIM_CAP_M3H) if self.pond > P.POND_MIN_M3 else 0.0
        if not use_plan:
            reclaim = min(reclaim, max(demand, 0.0))
        fresh = demand - reclaim + (P.PROCESS_TANK_M3 * P.PROCESS_TANK_START - self.tank) / 1.0
        fresh = min(max(fresh, 0.0), fresh_limit)
        interlock = False
        if self.tank + (fresh + reclaim - demand) * dt_h < P.PROCESS_TANK_M3 * P.PROCESS_TANK_TRIP:
            # interlock: the plant can only take what the pipes bring in
            allowed = (fresh + reclaim + (self.tank - P.PROCESS_TANK_M3 * P.PROCESS_TANK_TRIP) / dt_h + P.THICK_SAVING_M3_T * thick)
            new_total = max(0.0, min(total_feed, allowed / P.WATER_NET_M3_T))
            if new_total < total_feed - 1:
                if not self.out.get("interlock"):
                    self.event("Блокировка по воде: резервуар оборотной воды пуст, фабрика снижает питание")
                interlock = True
                k = new_total / total_feed if total_feed else 0.0
                feed = {f: v * k for f, v in feed.items()}
                total_feed = new_total
                thick = min(thick, total_feed)
                demand = P.WATER_NET_M3_T * total_feed - P.THICK_SAVING_M3_T * thick
        self.tank = min(P.PROCESS_TANK_M3, max(0.0, self.tank + (fresh + reclaim - demand) * dt_h))

        # power
        def loads():
            mill_kw = {m: 0.0 for m in P.MILLS}
            for m in running:
                mill_kw[m] = total_feed / lines * e_blend
            pit_kw = {f: (dig[f] * P.SHOVEL_KWH_T + P.SHOVEL_IDLE_KW) for f in P.FACE_IDS}
            other = {
                "crush": sum(dig.values()) * P.CRUSH_CONVEY_KWH_T,
                "plant": total_feed * P.PLANT_KWH_T,
                "thick": thick * P.THICK_KWH_T,
                "fresh": fresh * P.FRESH_KWH_M3,
                "reclaim": reclaim * P.RECLAIM_KWH_M3,
                "aux": P.AUX_KW,
            }
            total = sum(mill_kw.values()) + sum(pit_kw.values()) + sum(other.values())
            return mill_kw, pit_kw, other, total

        mill_kw, pit_kw, other_kw, total_kw = loads()
        total_kw *= 1 + rng.gauss(0, 0.004)
        if total_kw > power_limit * 1000 and running:
            # the grid's automatic load shedding trips the most loaded mill line
            victim = max(running, key=lambda m: mill_kw[m])
            self.mill_trip_until[victim] = self.hour + P.SHED_MINUTES / 60
            self.today["shed"] += 1
            self.event(f"Энергосистема: нагрузка {total_kw / 1000:.1f} МВт > лимита {power_limit:.0f} МВт, "
                       f"САОН отключила {victim.replace('mill-', 'мельницу №')} на {P.SHED_MINUTES:.0f} мин")
            running.remove(victim)
            lines_before = lines
            lines = max(len(running), 1)
            new_total = total_feed * len(running) / lines_before
            k = new_total / total_feed if total_feed else 0.0
            feed = {f: v * k for f, v in feed.items()}
            total_feed = new_total
            thick = min(thick, total_feed)
            mill_kw, pit_kw, other_kw, total_kw = loads()

        # stockpile balance
        for f in P.FACE_IDS:
            self.stock[f] = max(0.0, self.stock[f] + (dig[f] - feed[f]) * dt_h)

        # flotation
        if total_feed > 0:
            recovery = sum(feed[f] * P.FACES[f]["recovery"] for f in feed) / total_feed + rng.gauss(0, 0.3)
            feed_grade = sum(feed[f] * P.FACES[f]["grade"] for f in feed) / total_feed
        else:
            recovery, feed_grade = 0.0, 0.0
        copper = total_feed * feed_grade / 100 * recovery / 100

        # tailings and the pond
        water_to_tails = P.WATER_TO_TAILS_NORMAL * total_feed - P.THICK_SAVING_M3_T * thick
        free_water = water_to_tails - P.PORE_WATER_M3_T * total_feed
        loss = P.pond_loss_m3h(self.pond)
        self.pond = max(0.0, self.pond + (free_water - reclaim - loss) * dt_h)
        net_pond = free_water - reclaim - loss

        # day counters
        day_before = int(self.hour // 24)
        self.hour += dt_h
        if int(self.hour // 24) != day_before:
            self.event(f"Сутки {day_before + 1} закрыты: {self.today['copper']:.1f} т меди, {self.today['ore'] / 1000:.1f} тыс. т руды")
            self.today = {k: 0 if isinstance(v, int) else 0.0 for k, v in self.today.items()}
        self.today["copper"] += copper * dt_h
        self.today["ore"] += total_feed * dt_h
        self.today["fresh"] += fresh * dt_h
        self.today["interlock_h"] += dt_h if interlock else 0.0
        for f in P.FACE_IDS:
            self.today[f"dug_{f}"] += dig[f] * dt_h

        self.out = dict(
            fresh_limit=fresh_limit, power_limit=power_limit, running=running, e=e, e_blend=e_blend,
            dig=dig, feed=feed, total_feed=total_feed, thick=thick, demand=demand, reclaim=reclaim, fresh=fresh,
            interlock=interlock, mill_kw=mill_kw, pit_kw=pit_kw, other_kw=other_kw, total_kw=total_kw,
            recovery=recovery, feed_grade=feed_grade, copper=copper, water_to_tails=water_to_tails,
            free_water=free_water, loss=loss, net_pond=net_pond, use_plan=use_plan,
        )

    # -- twin state ----------------------------------------------------------
    def snapshot(self):
        o = self.out
        hod = self.hour % 24
        peak = self.flags["grid_peak"] and P.PEAK_HOURS[0] <= hod < P.PEAK_HOURS[1]

        def v(value, unit=None, nd=1):
            d = {"value": round(value, nd) if isinstance(value, float) else value}
            if unit:
                d["unit"] = unit
            return d

        things = {}
        active = [P.SCENARIOS[k] for k, on in self.flags.items() if on]
        things["complex"] = {
            "sim_clock": v(clock(self.hour)), "sim_hour": v(self.hour, "h", 3), "sim_day": v(int(self.hour // 24) + 1),
            "mode": v(self.mode), "plan_applied": v(bool(o["use_plan"])),
            "copper_tph": v(o["copper"], "t/h", 2), "copper_today": v(self.today["copper"], "t", 1),
            "ore_tph": v(o["total_feed"], "t/h", 0), "ore_today": v(self.today["ore"], "t", 0),
            "power_load": v(o["total_kw"] / 1000, "MW", 2), "power_limit": v(o["power_limit"], "MW", 1),
            "fresh_water": v(o["fresh"], "m3/h", 0), "fresh_limit": v(o["fresh_limit"], "m3/h", 0),
            "shed_today": v(self.today["shed"], "events"), "interlock_today": v(self.today["interlock_h"], "h", 2),
            "scenarios_active": v(len(active)), "scenarios_text": v("; ".join(active) or "нет"),
            "events": v("\n".join(self.events)),
        }
        things["pit"] = {"dig_tph": v(sum(o["dig"].values()), "t/h", 0)}
        for i, f in enumerate(P.FACE_IDS, 1):
            wi = self.wi(f)
            things[f] = {
                "grade": v(P.FACES[f]["grade"], "% Cu", 3), "bond_wi": v(wi, "kWh/t", 1),
                "grind_energy": v(o["e"][f], "kWh/t", 2), "dug_today": v(self.today[f"dug_{f}"], "t", 0),
                "hard_ore": v(f == "face-3" and self.flags["hard_ore"]),
            }
            rate = o["dig"][f]
            things[f"shovel-{i}"] = {
                "state": v("digging" if rate > 50 else "standby"), "rate": v(rate, "t/h", 0),
                "power": v(o["pit_kw"][f], "kW", 0),
            }
        crush = sum(o["dig"].values())
        things["crusher"] = {"state": v("running" if crush > 50 else "idle"), "throughput": v(crush, "t/h", 0),
                             "load": v(crush / P.CRUSHER_TPH * 100, "%", 1),
                             "power": v(crush * P.CRUSH_CONVEY_KWH_T * 0.6, "kW", 0)}
        things["conveyor"] = {"throughput": v(crush, "t/h", 0),
                              "power": v(crush * P.CRUSH_CONVEY_KWH_T * 0.4, "kW", 0)}
        total_stock = sum(self.stock.values())
        things["stockpile"] = {
            "total": v(total_stock, "t", 0), "fill": v(total_stock / P.STOCKPILE_CAP_T * 100, "%", 1),
            **{f"section_{i}": v(self.stock[f], "t", 0) for i, f in enumerate(P.FACE_IDS, 1)},
            "inflow": v(crush, "t/h", 0), "outflow": v(o["total_feed"], "t/h", 0),
        }
        lines = max(len(o["running"]), 1)
        for m in P.MILLS:
            state = self.mill_state(m)
            feed = o["total_feed"] / lines if m in o["running"] else 0.0
            if state == "running" and m not in o["running"]:
                state = "tripped"
            things[m] = {
                "state": v(state), "feed": v(feed, "t/h", 0), "power": v(o["mill_kw"][m] / 1000, "MW", 2),
                "load": v(o["mill_kw"][m] / P.MILL_KW * 100, "%", 1), "specific_energy": v(o["e_blend"], "kWh/t", 2),
                "trip_left": v(max(0.0, (self.mill_trip_until[m] - self.hour) * 60), "min", 0),
            }
        things["plant"] = {"feed": v(o["total_feed"], "t/h", 0),
                           "power": v((sum(o["mill_kw"].values()) + o["other_kw"]["plant"] + o["other_kw"]["thick"]) / 1000, "MW", 2)}
        things["flotation"] = {
            "feed": v(o["total_feed"], "t/h", 0), "feed_grade": v(o["feed_grade"], "% Cu", 3),
            "recovery": v(o["recovery"], "%", 1), "copper": v(o["copper"], "t/h", 2),
            "concentrate": v(o["copper"] / (P.CONC_GRADE / 100), "t/h", 1),
        }
        high = o["thick"] > 1
        solids = (P.TAILS_SOLIDS_NORMAL + (P.TAILS_SOLIDS_HIGH - P.TAILS_SOLIDS_NORMAL) * (o["thick"] / o["total_feed"])
                  if o["total_feed"] > 0 else P.TAILS_SOLIDS_NORMAL)
        things["thickener"] = {
            "mode": v("high-density" if high else "normal"), "underflow_solids": v(solids * 100, "%", 1),
            "high_density_feed": v(o["thick"], "t/h", 0), "water_to_tailings": v(o["water_to_tails"], "m3/h", 0),
            "power": v(o["other_kw"]["thick"], "kW", 0),
        }
        supply = o["fresh"] + o["reclaim"]
        hours_left = (self.tank - P.PROCESS_TANK_M3 * P.PROCESS_TANK_TRIP) / (o["demand"] - supply) if o["demand"] > supply + 1 else -1
        things["process-water"] = {
            "level": v(self.tank / P.PROCESS_TANK_M3 * 100, "%", 1), "volume": v(self.tank, "m3", 0),
            "demand": v(o["demand"], "m3/h", 0), "supply": v(supply, "m3/h", 0),
            "interlock": v(bool(o["interlock"])), "hours_to_trip": v(max(hours_left, 0.0) if hours_left >= 0 else -1.0, "h", 1),
        }
        things["water-intake"] = {
            "flow": v(o["fresh"], "m3/h", 0), "limit": v(o["fresh_limit"], "m3/h", 0),
            "utilisation": v(o["fresh"] / o["fresh_limit"] * 100, "%", 1), "dry_year": v(self.flags["dry_year"]),
            "power": v(o["other_kw"]["fresh"], "kW", 0), "today": v(self.today["fresh"], "m3", 0),
        }
        reserve_days = (self.pond - P.POND_MIN_M3) / (-o["net_pond"] * 24) if o["net_pond"] < -1 else -1.0
        things["tailings"] = {
            "pond_volume": v(self.pond, "m3", 0), "pond_depth": v(P.pond_depth_m(self.pond), "m", 3),
            "pond_area": v(P.pond_area_m2(self.pond) / 1e6, "km2", 3), "free_water_in": v(o["free_water"], "m3/h", 0),
            "losses": v(o["loss"], "m3/h", 0), "net_balance": v(o["net_pond"], "m3/h", 0),
            "reserve_days": v(reserve_days, "days", 0),
        }
        things["reclaim"] = {"flow": v(o["reclaim"], "m3/h", 0), "capacity": v(float(P.RECLAIM_CAP_M3H), "m3/h", 0),
                             "power": v(o["other_kw"]["reclaim"], "kW", 0)}
        things["substation"] = {
            "load": v(o["total_kw"] / 1000, "MW", 2), "limit": v(o["power_limit"], "MW", 1),
            "utilisation": v(o["total_kw"] / 10 / o["power_limit"], "%", 1),
            "headroom": v(o["power_limit"] - o["total_kw"] / 1000, "MW", 2), "peak_restriction": v(peak),
            "shed_today": v(self.today["shed"], "events"),
        }
        return things


def plan_from(planner):
    raw = prop(planner, "setpoint")
    if not isinstance(raw, dict) or prop(planner, "status") != "optimal":
        return None
    return raw


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    interval = float(os.environ.get("SIM_INTERVAL", "2"))
    speedup = float(os.environ.get("SIM_SPEEDUP", "60"))
    wait_for_ditto(["control", "planner"])
    client = connect_mqtt("limit-sim")
    sim = Complex(int(os.environ.get("SIM_SEED", "7")))
    log.info("simulating at %.0fx, a tick every %.1f s, starting %s", speedup, interval, clock(sim.hour))

    stop = False

    def on_signal(*_):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, on_signal)
    signal.signal(signal.SIGTERM, on_signal)

    plan = None
    ticks = 0
    while not stop:
        try:
            twins = get_things(NAMES_TO_READ)
            sim.apply_control(twins.get("control"))
            plan = plan_from(twins.get("planner"))
        except Exception as exc:     # Ditto busy: keep the last known control and plan
            log.warning("reading control/planner failed: %s", exc)
        sim.step(interval * speedup / 3600.0, plan)
        for name, features in sim.snapshot().items():
            publish_features(client, name, features)
        ticks += 1
        if ticks % 30 == 0:
            o = sim.out
            log.info("%s | ore %5.0f t/h | Cu %.2f t/h | %.1f/%.0f MW | fresh %4.0f/%4.0f m3/h | tank %4.1f%% | %s",
                     clock(sim.hour), o["total_feed"], o["copper"], o["total_kw"] / 1000, o["power_limit"],
                     o["fresh"], o["fresh_limit"], sim.tank / P.PROCESS_TANK_M3 * 100, sim.mode)
        time.sleep(interval)
    client.loop_stop()
    client.disconnect()
    return 0


if __name__ == "__main__":
    sys.exit(main())
