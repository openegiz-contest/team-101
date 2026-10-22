"""
The day plan as a linear program (scipy / HiGHS).

For each of the next 24 hours it chooses how much ore to dig on each face,
how much of each ore type to feed to the mills, how much tailings to thicken
in the high-density mode and how much fresh and reclaimed water to take,
so that copper in concentrate over the day is as large as possible within:

  * the substation power limit of every hour (the evening peak included),
  * the water intake permit, the reclaim pumps and the pond water balance,
  * the mill lines in operation (power and volumetric limits),
  * shovel rates, crusher capacity and the three stockpile sections.

The same model with the department rules imposed (pit shares fixed, no
stockpile buffering, no high-density thickening) gives the "proportional
cut" baseline, so the planner can say what its plan is worth in tonnes of
copper. Dual values say what one more MW or m³/h would be worth.
"""

import math

import numpy as np
from scipy.optimize import linprog

import params as P

H = 24
F = P.FACE_IDS
NF = len(F)

# Variables of one hour, in this order.
X, M, S = 0, NF, 2 * NF          # dig, mill feed, stockpile at end of hour (per face)
HD = 3 * NF                       # tonnes thickened in the high-density mode
FW, RW, V = HD + 1, HD + 2, HD + 3
NV = HD + 4
# Global slack variables after the hourly blocks.
SL_POND, SL_STOCK = H * NV, H * NV + 1
SL_BLEND = H * NV + 2              # one per hour
N = SL_BLEND + H

SLACK_PENALTY = 0.05              # t Cu per m³ or t of slack: ten times what any tonne of ore yields
STOCK_END_VALUE = 0.3             # ore left on the stockpile is worth 30 % of its copper today


def var(t, k):
    return t * NV + k


def setpoint(x, t, lines):
    return {
        "dig": {f: float(x[var(t, X + i)]) for i, f in enumerate(F)},
        "feed": {f: float(x[var(t, M + i)]) for i, f in enumerate(F)},
        "thick": float(x[var(t, HD)]),
        "fresh": float(x[var(t, FW)]),
        "reclaim": float(x[var(t, RW)]),
        "lines": lines,
    }


def durations(hour):
    first = math.ceil(hour) - hour
    return [first if first > 1e-6 else 1.0] + [1.0] * (H - 1)


def copper_t_per_t(face):
    f = P.FACES[face]
    return f["grade"] / 100.0 * f["recovery"] / 100.0


def solve(state, baseline=False):
    """
    state: hour (float), wi {face: Wi}, lines [24 ints], power_mw [24],
    fresh_m3h [24], stock {face: t}, pond_m3.

    Period 0 is the rest of the current clock hour, the others are whole
    clock hours, so hourly limits (the evening peak) apply exactly.
    """
    dur = durations(state["hour"])
    e = {f: P.grind_kwh_t(state["wi"][f]) for f in F}
    cu = {f: copper_t_per_t(f) for f in F}

    c = np.zeros(N)
    bounds = [(0, None)] * N
    a_ub, b_ub, tags_ub = [], [], []
    a_eq, b_eq = [], []

    def row():
        return np.zeros(N)

    pond_loss = P.pond_loss_m3h(state["pond_m3"])
    for t in range(H):
        lines = state["lines"][t]
        for i, f in enumerate(F):
            bounds[var(t, X + i)] = (0, P.FACES[f]["shovel_tph"])
            bounds[var(t, M + i)] = (0, None)
            bounds[var(t, S + i)] = (0, None)
            c[var(t, M + i)] -= cu[f] * dur[t]
            # stockpile section balance
            r = row()
            r[var(t, S + i)] = 1
            r[var(t, X + i)] = -dur[t]
            r[var(t, M + i)] = dur[t]
            if t:
                r[var(t - 1, S + i)] = -1
                b_eq.append(0.0)
            else:
                b_eq.append(state["stock"][f])
            a_eq.append(r)
        bounds[var(t, HD)] = (0, 0) if baseline else (0, None)
        bounds[var(t, FW)] = (0, state["fresh_m3h"][t])
        bounds[var(t, RW)] = (0, P.RECLAIM_CAP_M3H)
        bounds[var(t, V)] = (P.POND_MIN_M3, None)
        c[var(t, FW)] += 1e-6     # between equal plans, save fresh water
        for i in range(NF):        # ... and keep the pit working steadily rather than later
            c[var(t, X + i)] -= 1e-7 * (H - t)
        c[var(t, HD)] += 5e-7     # flocculant: thicken harder only when it pays

        def ub(r, b, tag):
            a_ub.append(r)
            b_ub.append(b)
            tags_ub.append((tag, t))

        r = row()
        for i in range(NF):
            r[var(t, S + i)] = 1
        ub(r, P.STOCKPILE_CAP_T, "stockpile")

        r = row()
        for i in range(NF):
            r[var(t, M + i)] = 1
        ub(r, P.MILL_MAX_TPH * lines, "mill_tph")

        r = row()
        for i, f in enumerate(F):
            r[var(t, M + i)] = e[f]
        ub(r, P.MILL_KW * lines, "mill_kw")

        r = row()
        for i in range(NF):
            r[var(t, X + i)] = 1
        ub(r, P.CRUSHER_TPH, "crusher")

        r = row()
        r[var(t, HD)] = 1
        for i in range(NF):
            r[var(t, M + i)] = -1
        ub(r, 0.0, "thickener")

        # water: make-up demand of the plant is covered by fresh + reclaim
        r = row()
        for i in range(NF):
            r[var(t, M + i)] = P.WATER_NET_M3_T
        r[var(t, HD)] = -P.THICK_SAVING_M3_T
        r[var(t, FW)] = -1
        r[var(t, RW)] = -1
        ub(r, 0.0, "water")

        # power, kW
        r = row()
        for i, f in enumerate(F):
            r[var(t, M + i)] = e[f] + P.PLANT_KWH_T
            r[var(t, X + i)] = P.CRUSH_CONVEY_KWH_T + P.SHOVEL_KWH_T
        r[var(t, HD)] = P.THICK_KWH_T
        r[var(t, FW)] = P.FRESH_KWH_M3
        r[var(t, RW)] = P.RECLAIM_KWH_M3
        fixed_kw = P.AUX_KW + P.SHOVEL_IDLE_KW * NF
        ub(r, state["power_mw"][t] * 1000 * P.PLAN_POWER_MARGIN - fixed_kw, "power")

        # pond: free water from the tailings minus reclaim, evaporation, seepage
        r = row()
        r[var(t, V)] = 1
        for i in range(NF):
            r[var(t, M + i)] = -(P.WATER_TO_TAILS_NORMAL - P.PORE_WATER_M3_T) * dur[t]
        r[var(t, HD)] = P.THICK_SAVING_M3_T * dur[t]
        r[var(t, RW)] = dur[t]
        if t:
            r[var(t - 1, V)] = -1
            b_eq.append(-pond_loss * dur[t])
        else:
            b_eq.append(state["pond_m3"] - pond_loss * dur[t])
        a_eq.append(r)

        # the long-term mine plan, hour by hour: each ore type keeps its plan
        # share of what is dug and of what is milled within the tolerance
        # (no high-grading, a steady blend for flotation)
        for i, f in enumerate(F):
            share = P.PIT_PLAN_SHARE[f]
            for sign, k in ((1, 1 + P.FACE_SHARE_TOLERANCE), (-1, 1 - P.FACE_SHARE_TOLERANCE)):
                for col in (X, M):
                    r = row()
                    for j in range(NF):
                        r[var(t, col + j)] -= sign * k * share
                    r[var(t, col + i)] += sign
                    r[SL_BLEND + t] = -1
                    ub(r, 0.0, "blend")
        c[SL_BLEND + t] = SLACK_PENALTY

        if baseline:
            # department rules: the pit digs in plan shares, the mills take
            # exactly what the pit sends, nothing is buffered
            total = sum(P.PIT_PLAN_SHARE.values())
            for i, f in enumerate(F):
                r = row()
                r[var(t, M + i)] = 1
                for j in range(NF):
                    r[var(t, M + j)] -= P.PIT_PLAN_SHARE[f] / total
                a_eq.append(r)
                b_eq.append(0.0)
                r = row()
                r[var(t, X + i)] = 1
                r[var(t, M + i)] = -1
                a_eq.append(r)
                b_eq.append(0.0)

    # end of day: keep the pond and stockpile reserves
    r = row()
    r[var(H - 1, V)] = -1
    r[SL_POND] = -1
    a_ub.append(r)
    b_ub.append(-max(P.POND_MIN_M3, state["pond_m3"] - P.POND_DAY_DRAWDOWN_M3))
    tags_ub.append(("pond_end", H - 1))
    c[SL_POND] = SLACK_PENALTY

    r = row()
    for i in range(NF):
        r[var(H - 1, S + i)] = -1
    r[SL_STOCK] = -1
    a_ub.append(r)
    b_ub.append(-min(P.STOCKPILE_MIN_END_T, sum(state["stock"].values())))
    tags_ub.append(("stock_end", H - 1))
    c[SL_STOCK] = SLACK_PENALTY

    if not baseline:
        for i, f in enumerate(F):
            c[var(H - 1, S + i)] -= STOCK_END_VALUE * cu[f]

    res = linprog(c, A_ub=np.array(a_ub), b_ub=np.array(b_ub), A_eq=np.array(a_eq), b_eq=np.array(b_eq),
                  bounds=bounds, method="highs")
    if res.status != 0:
        return {"ok": False, "message": res.message}

    x = res.x
    hours = [(int(state["hour"]) + t) % 24 for t in range(H)]
    sched = {"hour": hours, "ore": [], "pit": [], "copper": [], "power": [], "power_limit": [],
             "fresh": [], "fresh_limit": [], "reclaim": [], "thick": [], "pond": [], "stock": []}
    for t in range(H):
        ore = sum(x[var(t, M + i)] for i in range(NF))
        pit = sum(x[var(t, X + i)] for i in range(NF))
        kw = (sum(x[var(t, M + i)] * (e[f] + P.PLANT_KWH_T) + x[var(t, X + i)] * (P.CRUSH_CONVEY_KWH_T + P.SHOVEL_KWH_T)
                  for i, f in enumerate(F))
              + x[var(t, HD)] * P.THICK_KWH_T + x[var(t, FW)] * P.FRESH_KWH_M3 + x[var(t, RW)] * P.RECLAIM_KWH_M3
              + P.AUX_KW + P.SHOVEL_IDLE_KW * NF)
        sched["ore"].append(ore)
        sched["pit"].append(pit)
        sched["copper"].append(sum(x[var(t, M + i)] * cu[f] for i, f in enumerate(F)))
        sched["power"].append(kw / 1000)
        sched["power_limit"].append(state["power_mw"][t])
        sched["fresh"].append(x[var(t, FW)])
        sched["fresh_limit"].append(state["fresh_m3h"][t])
        sched["reclaim"].append(x[var(t, RW)])
        sched["thick"].append(x[var(t, HD)])
        sched["pond"].append(x[var(t, V)])
        sched["stock"].append(sum(x[var(t, S + i)] for i in range(NF)))

    # Shadow prices: t Cu per unit of right-hand side (minimising -Cu, so negate).
    duals = -res.ineqlin.marginals
    shadow = {}
    for (tag, t), d in zip(tags_ub, duals):
        shadow.setdefault(tag, [0.0] * H)
        if tag in ("pond_end", "stock_end", "blend"):
            continue
        shadow[tag][t] = d
    fresh_dual = [-res.upper.marginals[var(t, FW)] for t in range(H)]
    reclaim_dual = [-res.upper.marginals[var(t, RW)] for t in range(H)]

    return {
        "ok": True,
        "copper_day": float(sum(cph * d for cph, d in zip(sched["copper"], dur))),
        "dur": dur,
        "setpoint": setpoint(x, 0, state["lines"][0]),
        # the next clock hour, so the plant switches exactly at the boundary
        "next": setpoint(x, 1, state["lines"][1]),
        "until_hour": state["hour"] + dur[0],
        "schedule": sched,
        "shadow": {
            "power_kw": shadow["power"],          # t Cu per kW in that hour
            "mill_tph": shadow["mill_tph"],
            "mill_kw": shadow["mill_kw"],
            "crusher": shadow["crusher"],
            "stockpile": shadow["stockpile"],
            "fresh_m3h": fresh_dual,              # t Cu per m³/h in that hour
            "reclaim_m3h": reclaim_dual,
        },
        "grind_kwh_t": e,
    }
