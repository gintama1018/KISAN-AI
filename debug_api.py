"""Debug test for build_village_advisory"""
import sys, os, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv()
from app import build_village_advisory

try:
    d = build_village_advisory(20.0059, 73.7897, "Nashik", "grapes", "hi")
    print("SUCCESS")
    print("Drought:", d.get("drought", {}).get("level"))
    print("Soil:", d.get("soil_moisture"))
except Exception as e:
    print("ERROR:", e)
    traceback.print_exc()
