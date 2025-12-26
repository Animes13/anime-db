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

# 🔧 CONFIGURAÇÕES FINAIS (SEGURAS)
MAX_TMDB_ENRICH = 1800      # 🎬 filmes de anime reais
SLEEP_TIME = 0.25           # seguro para GitHub Actions
MIN_YEAR = 1980             # filmes clássicos também contam

def search_tmdb(item):
    titles = [
        item.get("titles", {}).get("english"),
        item.get("titles", {}).get("romaji"),
        *item.get("synonyms", [])
    ]

    titles = [t for t in titles if t]

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
            # 🎯 validações fortes
            if result.get("original_language") != "ja":
                continue

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

        # 🎯 TMDB SOMENTE PARA FILMES
        if item.get("format") != "MOVIE":
            continue

        # 🎯 evita sobrescrever match já válido
        if item.get("tmdb", {}).get("id"):
            continue

        year = item.get("year")
        if not year or year < MIN_YEAR:
            continue

        tmdb = search_tmdb(item)

        if tmdb:
            item["tmdb"] = {
                "id": tmdb.get("id"),
                "poster": tmdb.get("poster_path"),
                "backdrop": tmdb.get("backdrop_path"),
                "overview": tmdb.get("overview"),
                "vote_average": tmdb.get("vote_average"),
                "release_date": tmdb.get("release_date")
            }
            enriched += 1

        time.sleep(SLEEP_TIME)

    print(f"🎬 TMDB enriquecidos (filmes): {enriched}")
    return items


if __name__ == "__main__":
    with open("data/anilist_raw.json", encoding="utf-8") as f:
        items = json.load(f)

    items = enrich(items)

    with open("data/anilist_enriched.json", "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    print("✅ TMDB enrichment concluído")
