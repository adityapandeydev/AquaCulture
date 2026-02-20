"""
ml/pipeline.py

Purpose:
--------
This file is used ONLY for:

• Testing ML inference manually
• Validating models after training
• Debugging inference pipeline

Backend DOES NOT use this file.
Backend uses: ml/inference/predictor.py

This file safely calls predictor.py.
"""

import os
import numpy as np

# =========================
# PATH SETUP
# =========================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODELS_DIR = os.path.join(BASE_DIR, "models")


# =========================
# TEST FUNCTION
# =========================

def test_pipeline():
    """
    Runs full ML pipeline test using saved test data.
    """

    print("\n==============================")
    print("AquaTech ML Pipeline Test")
    print("==============================")

    # Import predictor safely
    from inference.predictor import predict_from_window

    # Load test dataset
    test_path = os.path.join(MODELS_DIR, "X1_test.npy")

    if not os.path.exists(test_path):
        raise FileNotFoundError(
            f"Test file not found: {test_path}"
        )

    print("\nLoading test window...")

    X1_test = np.load(test_path)

    latest_window = X1_test[0]

    print("Window shape:", latest_window.shape)

    print("\nRunning inference...")

    results = predict_from_window(latest_window)

    print("\nWater Forecast (Real Units):")
    print(np.array(results["water_forecast"]))

    print("\nNitrogen Forecast (Real Units):")
    print(np.array(results["nitrogen_forecast"]))

    print("\nPipeline test completed successfully.")
    print("==============================\n")


# =========================
# ENTRY POINT
# =========================

if __name__ == "__main__":
    test_pipeline()
