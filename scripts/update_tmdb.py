import os
import json
import requests
from datetime import datetime
from time import sleep

TMDB_API_KEY = os.getenv("TMDB_API_KEY")
BASE_URL = "https://api.themoviedb.org/3"

DATA_DIR = "data"
TV_FILE = f"{DATA_DIR}/anime_tv.json"
MOVIE_FILE = f"{DATA_DIR}/anime_movies.json"
META_FILE = f"{DATA_DIR}/meta.json"

HEADERS = {
    "Authorization": f"Bearer {TMDB_API_KEY}",
    "Content-Type": "application/json;charset=utf-8"
}

def fetch_all(endpoint, params):
    page = 1
    results = []
    total_pages = 1

    while page <= total_pages:
        params["page"] = page
        r = requests.get(f"{BASE_URL}/{endpoint}", headers=HEADERS, params=params)
        r.raise_for_status()
        data = r.json()

        total_pages = data.get("total_pages", 1)
        results.extend(data.get("results", []))

        page += 1
        sleep(0.25)  # evita rate limit

    return {
        "page": 1,
        "total_pages": total_pages,
        "total_results": len(results),
        "results": results
    }

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main():
    if not TMDB_API_KEY:
        raise RuntimeError("TMDB_API_KEY não configurada")

    os.makedirs(DATA_DIR, exist_ok=True)

    print("🔄 Buscando animes (TV)...")
    anime_tv = fetch_all(
        "discover/tv",
        {
            "with_genres": 16,
            "with_original_language": "ja",
            "sort_by": "popularity.desc"
        }
    )

    print("🔄 Buscando animes (Movies)...")
    anime_movies = fetch_all(
        "discover/movie",
        {
            "with_genres": 16,
            "with_original_language": "ja",
            "sort_by": "popularity.desc"
        }
    )

    save_json(TV_FILE, anime_tv)
    save_json(MOVIE_FILE, anime_movies)

    meta = {
        "source": "TMDB",
        "last_update": datetime.utcnow().isoformat() + "Z",
        "tv_count": anime_tv["total_results"],
        "movie_count": anime_movies["total_results"]
    }

    save_json(META_FILE, meta)

    print("✅ Atualização concluída")
    print(meta)

if __name__ == "__main__":
    main()
