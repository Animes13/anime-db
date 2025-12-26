import os
import requests
import json
import time
import re

TMDB_API = "https://api.themoviedb.org/3"
TOKEN = os.getenv("TMDB_TOKEN")

if not TOKEN:
    raise RuntimeError("❌ TMDB_TOKEN não definido nos Secrets")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json;charset=utf-8"
}

# 🔧 CONFIGURAÇÕES FINAIS
MAX_TMDB_ENRICH = 1800
SLEEP_TIME = 0.25
MIN_YEAR = 1980

used_tmdb_ids = set()

def normalize_title(title: str) -> str:
    title = title.lower()
    title = re.sub(r"[^\w\s]", "", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title

def search_tmdb(item):
    titles = [
        item.get("titles", {}).get("english"),
        item.get("titles", {}).get("romaji"),
        *item.get("synonyms", [])
    ]

    titles = [normalize_title(t) for t in titles if t]

    for title in titles:
        r = requests.get(
            f"{TMDB_API}/search/movie",
            headers=HEADERS,
            params={"query": title},
            timeout=15
        )

        if r.status_code != 200:
            continue

        for result in r.json().get("results", []):
            tmdb_id = result.get("id")
            if not tmdb_id or tmdb_id in used_tmdb_ids:
                continue

            # 🎯 idioma
            if result.get("original_language") != "ja":
                continue

            # 🎯 ano
            year = result.get("release_date", "")[:4]
            if item.get("year") and year:
                if abs(int(year) - int(item["year"])) > 1:
                    continue

            return result

    return None

def enrich(items):
    enriched = 0

    for item in items:
        if enriched >= MAX_TMDB_ENRICH:
            break

        # 🎯 apenas filmes
        if item.get("format") != "MOVIE":
            continue

        # 🎯 já enriquecido
        if item.get("tmdb", {}).get("id"):
            continue

        year = item.get("year")
        if not year or year < MIN_YEAR:
            continue

        tmdb = search_tmdb(item)

        if tmdb:
            tmdb_id = tmdb["id"]
            used_tmdb_ids.add(tmdb_id)

            item["tmdb"] = {
                "id": tmdb_id,
                "poster": tmdb.get("poster_path"),
                "backdrop": tmdb.get("backdrop_path"),
                "overview": tmdb.get("overview"),
                "vote_average": tmdb.get("vote_average"),
                "release_date": tmdb.get("release_date")
            }

            enriched += 1

        time.sleep(SLEEP_TIME)

    # 🧹 limpeza final
    for item in items:
        if not item.get("tmdb"):
            item.pop("tmdb", None)

    print(f"🎬 TMDB enriquecidos (filmes): {enriched}")
    return items

if __name__ == "__main__":
    with open("data/anilist_raw.json", encoding="utf-8") as f:
        items = json.load(f)

    items = enrich(items)

    with open("data/anilist_enriched.json", "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    print("✅ TMDB enrichment concluído")
