import os
import requests
import json
import time

TMDB_API = "https://api.themoviedb.org/3"
TOKEN = os.getenv("TMDB_TOKEN")

if not TOKEN:
    raise RuntimeError("❌ TMDB_TOKEN não definido")

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json;charset=utf-8"
}

SLEEP_TIME = 0.25
MIN_YEAR = 1970

# 🧱 tmdb padrão (TODOS TERÃO)
TMDB_EMPTY = {
    "id": None,
    "media_type": None,
    "poster": None,
    "backdrop": None,
    "overview": None,
    "vote_average": None,
    "release_date": None,
    "checked": False
}


def get_titles(item):
    titles = [
        item.get("titles", {}).get("english"),
        item.get("titles", {}).get("romaji"),
        item.get("titles", {}).get("native"),
        *item.get("synonyms", [])
    ]
    return list(dict.fromkeys(t for t in titles if t))


def search_tmdb(item):
    fmt = item.get("format")
    is_movie = fmt == "MOVIE"
    endpoint = "movie" if is_movie else "tv"

    for title in get_titles(item):
        r = requests.get(
            f"{TMDB_API}/search/{endpoint}",
            headers=HEADERS,
            params={"query": title},
            timeout=10
        )

        if r.status_code != 200:
            continue

        for result in r.json().get("results", []):
            if result.get("original_language") != "ja":
                continue

            date_field = "release_date" if is_movie else "first_air_date"
            year_tmdb = result.get(date_field, "")[:4]

            if item.get("year") and year_tmdb:
                if abs(int(year_tmdb) - int(item["year"])) > 1:
                    continue

            return {
                "id": result.get("id"),
                "media_type": endpoint,
                "poster": result.get("poster_path"),
                "backdrop": result.get("backdrop_path"),
                "overview": result.get("overview"),
                "vote_average": result.get("vote_average"),
                "release_date": result.get(date_field),
                "checked": True
            }

    return None


def enrich(items):
    for item in items:
        # ✅ garante tmdb para todos
        if "tmdb" not in item:
            item["tmdb"] = TMDB_EMPTY.copy()

        # 🔥 já testado
        if item["tmdb"].get("checked"):
            continue

        # 🎯 apenas formatos úteis
        if item.get("format") not in ("MOVIE", "TV"):
            item["tmdb"]["checked"] = True
            continue

        # ⛔ ano inválido
        year = item.get("year")
        if not year or year < MIN_YEAR:
            item["tmdb"]["checked"] = True
            continue

        tmdb = search_tmdb(item)

        if tmdb:
            item["tmdb"] = tmdb
        else:
            item["tmdb"]["checked"] = True

        # 💤 SEMPRE após request
        time.sleep(SLEEP_TIME)

    print("🎬 TMDB enrichment finalizado — sem limites artificiais")
    return items


if __name__ == "__main__":
    with open("data/anilist_raw.json", encoding="utf-8") as f:
        items = json.load(f)

    items = enrich(items)

    with open("data/anilist_enriched.json", "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    print("✅ Concluído — enriquecido até onde o TMDB permitiu")
