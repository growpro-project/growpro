# cd /home/pi/growpro/scripts
# python3 noaa_co2_trend.py


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


