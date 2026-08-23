import time


def main():
    import requests

    url = "https://overpass-api.de/api/interpreter"
    query = """[out:json][timeout:30];
way["railway"="rail"](20.0,75.0,25.0,80.0);
out body geom;
"""

    t0 = time.time()
    response = requests.post(
        url,
        data={"data": query},
        headers={"User-Agent": "RAKSHAK/1.0"},
    )
    print("Status:", response.status_code)

    if response.status_code == 200:
        data = response.json()
        elements = data.get("elements", [])
        elapsed = round(time.time() - t0, 2)
        print(f"Fetched {len(elements)} railway ways in box in {elapsed} seconds!")


if __name__ == "__main__":
    main()
