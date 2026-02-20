# ml/inference/predictor.py

import os
import json
import numpy as np
import joblib
import tensorflow as tf
import pandas as pd
from .risk_engine import compute_risk


# ============================
# PATH SETUP
# ============================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ML_DIR = os.path.dirname(BASE_DIR)
MODELS_DIR = os.path.join(ML_DIR, "models")


# ============================
# LOAD CONFIG
# ============================

with open(os.path.join(MODELS_DIR, "feature_columns.json"), "r") as f:
    FEATURE_COLUMNS = json.load(f)

CONFIG_PATH = os.path.join(MODELS_DIR, "model_config.json")

if os.path.exists(CONFIG_PATH):
    with open(CONFIG_PATH, "r") as f:
        MODEL_CONFIG = json.load(f)
    LOOKBACK = MODEL_CONFIG.get("lookback", 48)
else:
    LOOKBACK = 48


# ============================
# LOAD SCALER
# ============================

SCALER = joblib.load(
    os.path.join(MODELS_DIR, "scaler.save")
)


# ============================
# LOAD MODELS
# ============================

MODEL_WATER = tf.keras.models.load_model(
    os.path.join(MODELS_DIR, "model1_multivariate_lstm.keras")
)

MODEL_NITROGEN = tf.keras.models.load_model(
    os.path.join(MODELS_DIR, "model2_nitrogen_lstm.keras")
)


# ============================
# SCALING FUNCTIONS
# ============================

def scale_input_window(raw_window, timestamps):
    """
    raw_window shape: (lookback, 7)
    Order:
    [nitrate, ph, ammonia, temperature, do, turbidity, manganese]

    timestamps: list of datetime objects
    """

    raw_window = np.array(raw_window)

    nitrate = raw_window[:, 0]
    ph = raw_window[:, 1]
    ammonia = raw_window[:, 2]
    temperature = raw_window[:, 3]
    do = raw_window[:, 4]
    turbidity = raw_window[:, 5]
    manganese = raw_window[:, 6]

    # Time features
    hours = pd.to_datetime(timestamps).hour
    hour_sin = np.sin(2 * np.pi * hours / 24)
    hour_cos = np.cos(2 * np.pi * hours / 24)

    # Interaction features
    ammonia_ph = ammonia * ph
    ammonia_temp = ammonia * temperature

    # Stack features in training order
    full_features = np.column_stack([
        nitrate,
        ph,
        ammonia,
        temperature,
        do,
        turbidity,
        manganese,
        hour_sin,
        hour_cos,
        ammonia_ph,
        ammonia_temp
    ])

    scaled = SCALER.transform(full_features)

    return scaled


def inverse_scale_water(forecast_array):

    dummy = np.zeros((forecast_array.shape[0], len(FEATURE_COLUMNS)))

    water_cols = ["do", "temperature", "ph", "turbidity"]

    for i, col in enumerate(water_cols):
        idx = FEATURE_COLUMNS.index(col)
        dummy[:, idx] = forecast_array[:, i]

    inv = SCALER.inverse_transform(dummy)

    result = []

    for col in water_cols:
        idx = FEATURE_COLUMNS.index(col)
        result.append(inv[:, idx])

    return np.stack(result, axis=1)


def inverse_scale_nitrogen(forecast_array):

    dummy = np.zeros((forecast_array.shape[0], len(FEATURE_COLUMNS)))

    nitrogen_cols = ["ammonia", "nitrate"]

    for i, col in enumerate(nitrogen_cols):
        idx = FEATURE_COLUMNS.index(col)
        dummy[:, idx] = forecast_array[:, i]

    inv = SCALER.inverse_transform(dummy)

    result = []

    for col in nitrogen_cols:
        idx = FEATURE_COLUMNS.index(col)
        result.append(inv[:, idx])

    return np.stack(result, axis=1)


# ============================
# CORE PREDICTION FUNCTION
# ============================

def predict_from_window(raw_window, timestamps):
    """
    raw_window: (lookback, 7)
    timestamps: list of datetime objects
    """

    if raw_window.shape[0] != LOOKBACK:
        raise ValueError(
            f"Expected lookback {LOOKBACK}, got {raw_window.shape[0]}"
        )

    if len(timestamps) != LOOKBACK:
        raise ValueError(
            f"Timestamps length mismatch. Expected {LOOKBACK}"
        )

    # Step 1: scale input
    scaled_window = scale_input_window(raw_window, timestamps)

    # Step 2: expand batch dimension
    input_window = np.expand_dims(scaled_window, axis=0)

    # Step 3: water prediction
    water_scaled = MODEL_WATER.predict(input_window, verbose=0)[0]

    # Step 4: sequential injection
    nitrogen_input = input_window.copy()

    temp_idx = FEATURE_COLUMNS.index("temperature")
    ph_idx = FEATURE_COLUMNS.index("ph")

    nitrogen_input[0, -1, temp_idx] = water_scaled[0, 1]
    nitrogen_input[0, -1, ph_idx] = water_scaled[0, 2]

    # Step 5: nitrogen prediction
    nitrogen_scaled = MODEL_NITROGEN.predict(nitrogen_input, verbose=0)[0]

    # Step 6: inverse scaling
    water_real = inverse_scale_water(water_scaled)
    nitrogen_real = inverse_scale_nitrogen(nitrogen_scaled)
    risk_info = compute_risk(water_real, nitrogen_real)

    return {
        "water_forecast": water_real.tolist(),
        "nitrogen_forecast": nitrogen_real.tolist(),
        "risk": risk_info
    }


# ============================
# HEALTH CHECK
# ============================

def health_check():
    return {
        "status": "ready",
        "lookback": LOOKBACK,
        "features": FEATURE_COLUMNS
    }
