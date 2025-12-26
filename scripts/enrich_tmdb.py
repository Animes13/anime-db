# scripts/enrich_tmdb.py
import os
import requests
import json
import time

TMDB_API = "https://api.themoviedb.org/3"
TOKEN = os.getenv("TMDB_TOKEN")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json;charset=utf-8"
}

def search_tmdb(title, media_type):
    url = f"{TMDB_API}/search/{media_type}"
    params = {"query": title, "language": "pt-BR"}
    r = requests.get(url, headers=HEADERS, params=params, timeout=15)
    if r.status_code != 200:
        return None
    data = r.json().get("results")
    return data[0] if data else None

def enrich(items):
    for item in items:
        title = (
            item["titles"].get("english")
            or item["titles"].get("romaji")
        )

        media_type = "movie" if item["format"] == "MOVIE" else "tv"
        tmdb = search_tmdb(title, media_type)

        if tmdb:
            item["tmdb"] = {
                "id": tmdb["id"],
                "poster": tmdb.get("poster_path"),
                "backdrop": tmdb.get("backdrop_path"),
                "overview": tmdb.get("overview")
            }

        time.sleep(0.25)

    return items

if __name__ == "__main__":
    with open("data/anilist_raw.json", encoding="utf-8") as f:
        items = json.load(f)

    items = enrich(items)

    with open("data/anilist_enriched.json", "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    print("✅ TMDB enrichment concluído")
