import os
import requests
import json
import time
from itertools import cycle
from concurrent.futures import ThreadPoolExecutor

TMDB_API = "https://api.themoviedb.org/3"

# 🔑 Pool de tokens TMDB (4)
TOKENS = [
    os.getenv("TMDB_TOKEN_1"),
    os.getenv("TMDB_TOKEN_2"),
    os.getenv("TMDB_TOKEN_3"),
    os.getenv("TMDB_TOKEN_4"),
]

TOKENS = [t for t in TOKENS if t]
if len(TOKENS) < 4:
    raise RuntimeError("❌ É necessário configurar 4 TMDB_TOKENs")

token_cycle = cycle(TOKENS)

def make_headers():
    return {
        "Authorization": f"Bearer {next(token_cycle)}",
        "Content-Type": "application/json;charset=utf-8"
    }

# ⚙️ CONFIGURAÇÕES SEGURAS
MAX_WORKERS = 4        # seguro para GitHub Actions
SLEEP_TIME = 0.15      # evita bursts
MIN_YEAR = 1970

# 🧱 tmdb padrão (TODOS TERÃO)
TMDB_EMPTY = {
    "id": None,
    "media_type": None,   # movie | tv
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
    # 🔁 deduplicação mantendo ordem
    return list(dict.fromkeys(t for t in titles if t))


def search_tmdb(item):
    fmt = item.get("format")
    is_movie = fmt == "MOVIE"
    endpoint = "movie" if is_movie else "tv"

    for title in get_titles(item):
        try:
            r = requests.get(
                f"{TMDB_API}/search/{endpoint}",
                headers=make_headers(),
                params={"query": title},
                timeout=10
            )

            if r.status_code != 200:
                continue

            for result in r.json().get("results", []):
                # 🎌 anime geralmente japonês
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

        except Exception:
            return None

    return None


def enrich_one(item):
    # ✅ garante tmdb
    if "tmdb" not in item:
        item["tmdb"] = TMDB_EMPTY.copy()

    # 🔒 já testado
    if item["tmdb"].get("checked"):
        return item

    # 🎯 apenas formatos úteis
    if item.get("format") not in ("MOVIE", "TV"):
        item["tmdb"]["checked"] = True
        return item

    # ⛔ ano inválido
    year = item.get("year")
    if not year or year < MIN_YEAR:
        item["tmdb"]["checked"] = True
        return item

    tmdb = search_tmdb(item)

    if tmdb:
        item["tmdb"] = tmdb
    else:
        item["tmdb"]["checked"] = True

    # 💤 controle de taxa real
    time.sleep(SLEEP_TIME)
    return item


def enrich(items):
    # ⚡ mantém ordem original
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        return list(executor.map(enrich_one, items))


if __name__ == "__main__":
    with open("data/anilist_raw.json", encoding="utf-8") as f:
        items = json.load(f)

    items = enrich(items)

    with open("data/anilist_enriched.json", "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

    print("✅ TMDB enrichment concluído — até onde o TMDB permitiu")
