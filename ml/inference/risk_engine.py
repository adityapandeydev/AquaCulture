import numpy as np


# ============================
# PARAMETER CLASSIFICATION
# ============================

def classify_do(value):
    if value >= 5:
        return 0
    elif 4 <= value < 5:
        return 1
    else:
        return 2


def classify_temp(value):
    if 26 <= value <= 32:
        return 0
    elif 22 <= value < 26 or 32 < value <= 34:
        return 1
    else:
        return 2


def classify_ph(value):
    if 7.5 <= value <= 8.5:
        return 0
    elif 7.0 <= value < 7.5 or 8.5 < value <= 9.0:
        return 1
    else:
        return 2   # anything outside 7.0–9.0 is critical


def classify_ammonia(value):
    if value < 0.1:
        return 0
    elif 0.1 <= value <= 0.25:
        return 1
    else:
        return 2


def classify_nitrate(value):
    if value < 50:
        return 0
    elif 50 <= value <= 100:
        return 1
    else:
        return 2


# ============================
# COMPOSITE RISK ENGINE
# ============================

def compute_risk(water_forecast, nitrogen_forecast):

    weights = {
        "do": 2.0,
        "temperature": 1.5,
        "ph": 2.0,        # Increased weight
        "ammonia": 2.0,
        "nitrate": 1.0
    }

    risk_scores = []
    risk_states = []

    for t in range(len(water_forecast)):

        do = water_forecast[t][0]
        temp = water_forecast[t][1]
        ph = water_forecast[t][2]

        ammonia = nitrogen_forecast[t][0]
        nitrate = nitrogen_forecast[t][1]

        do_r = classify_do(do)
        temp_r = classify_temp(temp)
        ph_r = classify_ph(ph)
        ammonia_r = classify_ammonia(ammonia)
        nitrate_r = classify_nitrate(nitrate)

        # -------------------------
        # HARD CRITICAL OVERRIDE
        # -------------------------
        if (
            do_r == 2 or
            ph_r == 2 or
            ammonia_r == 2
        ):
            risk_scores.append(10)
            risk_states.append("Critical")
            continue

        # -------------------------
        # COMPOSITE SCORE
        # -------------------------
        score = (
            weights["do"] * do_r +
            weights["temperature"] * temp_r +
            weights["ph"] * ph_r +
            weights["ammonia"] * ammonia_r +
            weights["nitrate"] * nitrate_r
        )

        risk_scores.append(score)

        if score >= 5:
            risk_states.append("Critical")
        elif score >= 2.5:
            risk_states.append("Warning")
        else:
            risk_states.append("Safe")

    # -------------------------
    # LEAD TIME
    # -------------------------
    if "Critical" in risk_states:
        first_critical = risk_states.index("Critical")
        lead_time = first_critical + 1
    else:
        lead_time = None

    return {
        "risk_scores": risk_scores,
        "risk_states": risk_states,
        "lead_time_steps": lead_time
    }
