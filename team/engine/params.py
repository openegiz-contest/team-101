"""
Parameters of the «Рудник под лимитом» complex: one place for every number
the simulator and the planner use. Sources and reasoning are in
SUBMISSION.md, section «Data and Assumptions»; the comments here only say
what each number means.

Units: tonnes, hours, kW, m³. Rates are per hour.
"""

import math

NS = "kz.limit"


def tid(name):
    return f"{NS}:{name}"


# --- Pit: three faces, one electric rope shovel on each ----------------------
# grade: % Cu in ore; wi: Bond ball-mill work index, kWh/t;
# recovery: flotation recovery of that ore type, %; shovel_tph: sustained
# digging rate of the shovel on that face.
FACES = {
    "face-1": {"name": "Забой 1 · Северный борт", "grade": 0.36, "wi": 13.0, "recovery": 88.0, "shovel_tph": 1600},
    "face-2": {"name": "Забой 2 · Восточный борт", "grade": 0.29, "wi": 11.5, "recovery": 85.0, "shovel_tph": 1600},
    "face-3": {"name": "Забой 3 · Южный, нижний горизонт", "grade": 0.47, "wi": 15.5, "recovery": 89.0, "shovel_tph": 1400},
}
FACE_IDS = list(FACES)
HARD_ORE_WI = 19.5            # face-3 under the «hard ore» scenario
# The mine department's daily plan: shares of each face in the pit output.
PIT_PLAN_SHARE = {"face-1": 0.40, "face-2": 0.35, "face-3": 0.25}
PIT_PLAN_TPH = 3300.0
FACE_SHARE_TOLERANCE = 0.20  # in every hour each ore type stays within ±20 % of its plan share
SHOVEL_KWH_T = 0.625          # ~1 MW per shovel at 1 600 t/h
SHOVEL_IDLE_KW = 150.0

# --- Crushing and conveying ---------------------------------------------------
CRUSHER_TPH = 3600.0
CRUSH_CONVEY_KWH_T = 0.6      # gyratory crusher + 3 km overland conveyor

# --- Coarse ore stockpile, kept in three sections by ore type ---------------
STOCKPILE_CAP_T = 60000.0
STOCKPILE_START_T = {"face-1": 12000.0, "face-2": 10500.0, "face-3": 7500.0}
STOCKPILE_MIN_END_T = 20000.0  # the plan may not run the stockpile below this by the end of the day

# --- Grinding: two SAG + ball mill lines -------------------------------------
MILLS = ["mill-1", "mill-2"]
MILL_KW = 22000.0             # usable grinding power per line
MILL_MAX_TPH = 1600.0         # volumetric / pumping limit per line
F80_UM = 100000.0             # SAG feed, 80 % passing
P80_UM = 150.0                # flotation feed, 80 % passing
SAG_CIRCUIT_FACTOR = 1.35     # SAG-ball circuits need more than the Bond estimate


def grind_kwh_t(wi):
    """Specific grinding energy from Bond's third law, kWh/t."""
    return SAG_CIRCUIT_FACTOR * 10.0 * wi * (1.0 / math.sqrt(P80_UM) - 1.0 / math.sqrt(F80_UM))


# --- Flotation and the rest of the plant ------------------------------------
PLANT_KWH_T = 4.5             # flotation, regrind, thickeners, slurry pumps
CONC_GRADE = 24.0             # % Cu in concentrate

# --- Water -------------------------------------------------------------------
TAILS_SOLIDS_NORMAL = 0.55    # tailings thickener underflow, by weight
TAILS_SOLIDS_HIGH = 0.62      # with extra flocculant and slower rakes
WATER_TO_TAILS_NORMAL = 1 / TAILS_SOLIDS_NORMAL - 1    # m³ per t ore
WATER_TO_TAILS_HIGH = 1 / TAILS_SOLIDS_HIGH - 1
THICK_SAVING_M3_T = WATER_TO_TAILS_NORMAL - WATER_TO_TAILS_HIGH
THICK_KWH_T = 0.4             # extra energy of the high-density mode
OTHER_WATER_LOSS_M3_T = 0.05  # concentrate moisture, dust suppression
WATER_NET_M3_T = WATER_TO_TAILS_NORMAL + OTHER_WATER_LOSS_M3_T   # make-up per t ore
PORE_WATER_M3_T = 0.32        # locked in the settled tailings, never comes back

FRESH_LIMIT_M3H = 1750.0      # water intake permit
DRY_YEAR_FACTOR = 0.70        # «dry year»: intake cut by 30 %
FRESH_KWH_M3 = 1.8            # long pipeline from the canal
RECLAIM_CAP_M3H = 1100.0      # three reclaim pumps on the pond barge
RECLAIM_KWH_M3 = 0.45

PROCESS_TANK_M3 = 4000.0
PROCESS_TANK_START = 0.70
PROCESS_TANK_TRIP = 0.10      # below this the plant interlock cuts feed

POND_START_M3 = 3.2e6
POND_MIN_M3 = 2.0e6           # below this the barge pumps cannot draw
POND_AREA_M2 = 1.6e6          # at POND_START_M3 (2 m average depth)
POND_DAY_DRAWDOWN_M3 = 15000.0  # the plan may draw the pond down by this much a day
EVAPORATION_MM_DAY = 3.0      # October, Central Kazakhstan
SEEPAGE_M3H = 40.0


def pond_area_m2(volume):
    return POND_AREA_M2 * math.sqrt(max(volume, 0.0) / POND_START_M3)


def pond_depth_m(volume):
    return max(volume, 0.0) / max(pond_area_m2(volume), 1.0)


def pond_loss_m3h(volume):
    return pond_area_m2(volume) * EVAPORATION_MM_DAY / 1000.0 / 24.0 + SEEPAGE_M3H


# --- Power ---------------------------------------------------------------------
GRID_LIMIT_MW = 78.0          # contracted capacity of the main substation
GRID_PEAK_LIMIT_MW = 58.0     # «evening peak» scenario
PEAK_HOURS = (18, 22)         # [start, end) local time
AUX_KW = 2000.0               # workshops, lighting, offices, HVAC
PLAN_POWER_MARGIN = 0.98      # the plan keeps 2 % headroom for fluctuations
SHED_MINUTES = 40.0           # a mill line tripped by load shedding stays off this long
MILL_REPAIR_HOURS = 36.0      # «mill 2 under repair» scenario


def default_power_limit_mw(hour, peak_active):
    if peak_active and PEAK_HOURS[0] <= hour % 24 < PEAK_HOURS[1]:
        return GRID_PEAK_LIMIT_MW
    return GRID_LIMIT_MW


# --- Scenarios (features of the control twin) --------------------------------
SCENARIOS = {
    "dry_year": "Маловодный год: водозабор −30 %",
    "grid_peak": "Энергосистема: лимит 58 МВт в пик 18:00–22:00",
    "mill2_repair": "Мельница №2 остановлена на ремонт",
    "hard_ore": "Твёрдая руда в забое №3 (Wi 19,5)",
}
