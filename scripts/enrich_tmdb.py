import os
import requests
import json
import time

TMDB_API = "https://api.themoviedb.org/3"
TOKEN = os.getenv("TMDB_TOKEN")

if not TOKEN:
    raise RuntimeError("❌ TMDB_TOKEN não definido nos Secrets")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json;charset=utf-8"
}

# 🔧 CONFIGURAÇÕES IMPORTANTES
MAX_TMDB_ENRICH = 3000      # 🔥 limite total (ajuste se quiser)
SLEEP_TIME = 0.15           # delay seguro para GitHub Actions
MIN_YEAR = 2000             # ignora animes muito antigos

def search_tmdb(item, media_type):
    titles = [
        item["titles"].get("english"),
        item["titles"].get("romaji"),
        *item.get("synonyms", [])
    ]

    titles = [t for t in titles if t]

    for title in titles:
        r = requests.get(
            f"{TMDB_API}/search/{media_type}",
            headers=HEADERS,
            params={"query": title},
            timeout=15
        )

        if r.status_code != 200:
            continue

        for result in r.json().get("results", []):
            # 🎯 validações fortes
            if result.get("original_language") != "ja":
                continue

            year = (
                result.get("release_date", "")[:4]
                if media_type == "movie"
                else result.get("first_air_date", "")[:4]
            )

            if item["year"] and year:
                if abs(int(year) - int(item["year"])) > 1:
                    continue

            return result

    return None


def enrich(items):
    enriched = 0

    for item in items:
        if enriched >= MAX_TMDB_ENRICH:
            break

        # 🎯 só TV e MOVIE
        if item.get("format") not in ("TV", "MOVIE"):
            continue

        # 🎯 ignora muito antigos
        year = item.get("year")
        if not year or year < MIN_YEAR:
            continue

        title = (
            item.get("titles", {}).get("english")
            or item.get("titles", {}).get("romaji")
        )

        if not title:
            continue

        media_type = "movie" if item["format"] == "MOVIE" else "tv"
        tmdb = search_tmdb(title, media_type)

        if tmdb:
            item["tmdb"] = {
                "id": tmdb.get("id"),
                "poster": tmdb.get("poster_path"),
                "backdrop": tmdb.get("backdrop_path"),
                "overview": tmdb.get("overview"),
                "vote_average": tmdb.get("vote_average"),
                "release_date": tmdb.get("release_date") or tmdb.get("first_air_date")
            }
            enriched += 1

        time.sleep(SLEEP_TIME)

    print(f"🎬 TMDB enriquecidos: {enriched}")
    return items


if __name__ == "__main__":
    with open("data/anilist_raw.json", encoding="utf-8") as f:
        items = json.load(f)

    items = enrich(items)

    with open("data/anilist_enriched.json", "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    print("✅ TMDB enrichment concluído")
