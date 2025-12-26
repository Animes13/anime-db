# -*- coding: utf-8 -*-
import os
import json
import time
import requests
from datetime import datetime

BASE_URL = "https://api.themoviedb.org/3"
DATA_DIR = "data"

TMDB_TOKEN = os.environ.get("TMDB_TOKEN")
if not TMDB_TOKEN:
    raise RuntimeError("TMDB_TOKEN não configurado")

HEADERS = {
    "Authorization": f"Bearer {TMDB_TOKEN}",
    "Content-Type": "application/json;charset=utf-8"
}

def fetch_all(endpoint, params):
    results = []
    page = 1
    total_pages = 1

    while page <= total_pages:
        params["page"] = page
        r = requests.get(
            f"{BASE_URL}/{endpoint}",
            headers=HEADERS,
            params=params,
            timeout=20
        )
        r.raise_for_status()

        data = r.json()
        total_pages = data.get("total_pages", 1)

        print(f"📄 {endpoint} página {page}/{total_pages}")

        results.extend(data.get("results", []))
        page += 1

        # rate limit seguro
        time.sleep(0.25)

    return {
        "page": 1,
        "total_pages": total_pages,
        "total_results": len(results),
        "results": results
    }

def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def main():
    print("🔄 Buscando animes (TV)...")
    anime_tv = fetch_all(
        "discover/tv",
        {
            "with_genres": 16,
            "with_original_language": "ja",
            "sort_by": "popularity.desc"
        }
    )

    print("🎬 Buscando filmes de anime...")
    anime_movies = fetch_all(
        "discover/movie",
        {
            "with_genres": 16,
            "with_original_language": "ja",
            "sort_by": "popularity.desc"
        }
    )

    save_json(f"{DATA_DIR}/anime_tv.json", anime_tv)
    save_json(f"{DATA_DIR}/anime_movies.json", anime_movies)

    meta = {
        "source": "TMDB",
        "last_update": datetime.utcnow().isoformat() + "Z",
        "tv_count": anime_tv["total_results"],
        "movie_count": anime_movies["total_results"]
    }

    save_json(f"{DATA_DIR}/meta.json", meta)

    print("✅ Atualização finalizada com sucesso")

if __name__ == "__main__":
    main()
