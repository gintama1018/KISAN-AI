"""Quick end-to-end pipeline test — run with: python test_pipeline.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from data.satellite import fetch_all_satellite_data
from data.ndvi import fetch_ndvi
from ai.drought import drought_risk_model
from ai.pest import pest_risk_model
from ai.sowing import sowing_window_model
from ai.translate import build_full_advisory

print("=== KISAN AI — PIPELINE TEST ===\n")
for village, lat, lon, crop in [
    ("Nashik (Maharashtra)", 20.0059, 73.7897, "grapes"),
    ("Varanasi (UP)", 25.3176, 82.9739, "wheat"),
    ("Anantapur (AP)", 14.6819, 77.6006, "groundnut"),
]:
    print(f"--- {village} ---")
    w = fetch_all_satellite_data(lat, lon)
    n = fetch_ndvi(lat, lon)

    d = drought_risk_model(w["soil_moisture"], n["ndvi"], w["rainfall_7d"], w["et0_today"], crop)
    p = pest_risk_model(w["temp_max"], w["temp_min"], w["humidity"], n["ndvi"], n["ndvi_7d_ago"], crop, w["rainfall_today"])
    s = sowing_window_model(w["soil_temp"], w.get("forecast_rainfall", []), w["et0_today"], w["soil_moisture"], crop, w["rainfall_today"])

    print(f"  Source:  {w['source']}")
    print(f"  Soil:    {w['soil_moisture']:.1f}%  | Temp: {w['temp_max']:.1f}°C | Rain7d: {w['rainfall_7d']:.1f}mm | ET0: {w['et0_today']:.2f}mm/d")
    print(f"  NDVI:    {n['ndvi']:.2f}  ({n.get('source', 'est')})")
    print(f"  DROUGHT: {d['level']} (score={d['score']}) — {d['action'][:60]}...")
    print(f"  PEST:    {p['pest']} [{p['risk']}]")
    print(f"  SOWING:  {s['decision']}")
    print()
    advisory = build_full_advisory(d, p, s, "hi", village.split("(")[0].strip(), crop)
    print(advisory)
    print()

print("=== ALL TESTS PASSED ===")
