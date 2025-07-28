# cd /home/pi/growpro/scripts
# python3 noaa_co2_trend.py


# import requests

# def get_latest_smoothed_co2():
#     url = "https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_trend_gl.txt"
#     try:
#         response = requests.get(url, timeout=10)
#         response.raise_for_status()
#         lines = response.text.splitlines()

#         # Nur Zeilen mit Daten (keine Kommentare), mit genau 5 Spalten
#         data_lines = [
#             line.strip() for line in lines
#             if line and not line.startswith("#") and len(line.strip().split()) == 5
#         ]

#         # Letzte Zeile nehmen
#         last_line = data_lines[-1]
#         parts = last_line.split()
#         date = f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
#         smoothed_value = float(parts[3])
#         trend_value = float(parts[4])

#         # print(f"📅 Letzter Eintrag: {date}")
#         # print(f"📈 Smoothed CO₂-Wert: {smoothed_value} ppm")
#         # print(f"📉 Trend CO₂-Wert: {trend_value} ppm")

#         return smoothed_value

#     except Exception as e:
#         print(f"❌ Fehler beim Abrufen oder Verarbeiten: {e}")
#         return None

# # Beispielaufruf
# latest_co2 = get_latest_smoothed_co2()
# latest_co2 = int(round(latest_co2)) # → 425

# print(latest_co2)

import requests
import json

def get_latest_smoothed_co2():
    url = "https://gml.noaa.gov/webdata/ccgg/trends/co2/co2_trend_gl.txt"
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        lines = response.text.splitlines()

        data_lines = [
            line.strip() for line in lines
            if line and not line.startswith("#") and len(line.strip().split()) == 5
        ]

        last_line = data_lines[-1]
        parts = last_line.split()
        date = f"{parts[0]}-{parts[1].zfill(2)}-{parts[2].zfill(2)}"
        smoothed_value = float(parts[3])
        trend_value = float(parts[4])

        return smoothed_value, date

    except Exception as e:
        #print(f"ERROR: {e}")
        return None, None

if __name__ == "__main__":
    latest_co2, date = get_latest_smoothed_co2()
    if latest_co2 is not None and date is not None:
        result = {
            "co2_smoothed": int(round(latest_co2)),
            "date": date
        }
        print(json.dumps(result))
    else:
        result = {
            "co2_smoothed": None,
            "date": None
        }
        print(json.dumps(result))
        #print(json.dumps({"error": "Failed to retrieve data"}))



