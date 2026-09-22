import numpy as np
import datetime
from typing import List, Dict, Any, Optional

class TrendForecaster:
    """
    Transparent trend forecasting engine for environmental telemetry.
    Uses polynomial and rolling weighted least-squares regression to compute
    instantaneous rate of change and forecast +1m, +5m, +15m values with
    confidence bands based on residual variance.
    """
    def __init__(self, window_size: int = 15):
        self.window_size = window_size

    def forecast(self, readings: List[Dict[str, Any]], variable: str = "temperature") -> Dict[str, Any]:
        """
        Takes recent telemetry readings (sorted chronologically) and computes
        rate of change, future projections, and confidence intervals.
        """
        if not readings or len(readings) < 3:
            default_val = readings[-1]["value"] if readings else 23.5
            return {
                "variable": variable,
                "current_value": default_val,
                "trend_slope": 0.0,
                "horizons": {
                    "+1m": {"predicted": default_val, "lower": default_val - 0.5, "upper": default_val + 0.5},
                    "+5m": {"predicted": default_val, "lower": default_val - 1.2, "upper": default_val + 1.2},
                    "+15m": {"predicted": default_val, "lower": default_val - 2.5, "upper": default_val + 2.5}
                },
                "confidence": 0.65,
                "is_abnormal_trend": False,
                "explanation": f"Insufficient data points for robust trend fitting (n={len(readings)})."
            }

        # Filter and extract values and time intervals
        recent = readings[-self.window_size:]
        values = np.array([r["value"] for r in recent], dtype=float)
        n = len(values)
        
        # X: time steps in units of ~2 seconds or minutes
        x = np.arange(n, dtype=float)
        
        # Weighted linear regression (give more weight to latest readings)
        weights = np.linspace(0.5, 1.0, n)
        poly, residuals, _, _, _ = np.polyfit(x, values, 1, w=weights, full=True)
        slope = poly[0]
        intercept = poly[1]

        # Convert slope to per-minute rate of change (assuming ~2s between samples = 30 samples/min)
        samples_per_minute = 30.0
        raw_slope_per_min = float(slope * samples_per_minute)
        
        # Physical clamp on rate of change: max ±8.0 °C/min or ±80 ppm/min
        max_rate = 8.0 if variable == "temperature" else 80.0
        rate_of_change_per_min = round(float(np.clip(raw_slope_per_min, -max_rate, max_rate)), 2)

        current_val = round(float(values[-1]), 2)
        
        # Residual standard error
        fitted = poly[0] * x + poly[1]
        std_err = float(np.std(values - fitted)) if n > 2 else 0.2

        # Forecast horizons in minutes: +1m, +5m, +15m
        p1 = round(float(current_val + (rate_of_change_per_min * 1.0)), 2)
        p5 = round(float(current_val + (rate_of_change_per_min * 5.0)), 2)
        p15 = round(float(current_val + (rate_of_change_per_min * 15.0)), 2)

        # Confidence bounds widen with time horizon
        ci1 = round(1.96 * max(0.2, std_err * 1.2), 2)
        ci5 = round(1.96 * max(0.5, std_err * 2.5), 2)
        ci15 = round(1.96 * max(1.0, std_err * 4.0), 2)

        # Confidence score (0.5 to 0.95) degrades with high residual variance
        confidence = round(max(0.50, min(0.95, 1.0 - (std_err / (abs(current_val) + 1e-5)))), 2)

        # Determine if trend is alarming
        is_abnormal = False
        if variable == "temperature" and rate_of_change_per_min > 1.5:
            is_abnormal = True
        elif variable == "gas" and rate_of_change_per_min > 15.0:
            is_abnormal = True

        explanation = (
            f"Current {variable} is {current_val} with a trajectory of "
            f"{'+' if rate_of_change_per_min > 0 else ''}{rate_of_change_per_min}/min. "
            f"Model projects {p5} (+5 min) with ±{ci5} 95% uncertainty interval."
        )

        return {
            "variable": variable,
            "current_value": current_val,
            "trend_slope": rate_of_change_per_min,
            "horizons": {
                "+1m": {"predicted": p1, "lower": round(p1 - ci1, 2), "upper": round(p1 + ci1, 2)},
                "+5m": {"predicted": p5, "lower": round(p5 - ci5, 2), "upper": round(p5 + ci5, 2)},
                "+15m": {"predicted": p15, "lower": round(p15 - ci15, 2), "upper": round(p15 + ci15, 2)}
            },
            "confidence": confidence,
            "is_abnormal_trend": is_abnormal,
            "explanation": explanation
        }

# Global forecaster instance
forecaster = TrendForecaster()
