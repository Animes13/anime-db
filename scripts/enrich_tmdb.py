# -*- coding: utf-8 -*-

import os
import re
import json
import time
import unicodedata
import requests
from itertools import cycle
from concurrent.futures import ThreadPoolExecutor

# ==================================================
# CONFIG TMDB
# ==================================================

TMDB_API = "https://api.themoviedb.org/3"

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

# ==================================================
# CONFIGURAÇÕES
# ==================================================

MAX_WORKERS = 4
SLEEP_TIME = 0.15

TMDB_EMPTY = {
    "id": None,
    "media_type": None,
    "season": None,
    "poster": None,
    "backdrop": None,
    "overview": None,
    "vote_average": None,
    "release_date": None,
    "checked": False
}

# ==================================================
# NORMALIZAÇÃO DE TÍTULOS
# ==================================================

ROMAN = {
    " i ": " 1 ",
    " ii ": " 2 ",
    " iii ": " 3 ",
    " iv ": " 4 ",
    " v ": " 5 ",
    " vi ": " 6 ",
}

STOPWORDS = [
    r"\b(first|second|third|fourth|final)\b",
    r"\b(stage|part|season|cour)\b",
    r"\b(ova|ona|special|episode|ep)\b",
    r"\b(tv|the animation|anime)\b",
]

def normalize_title(title: str):
    original = title.lower()

    season = None
    m = re.search(r"(season|stage|part)\s*(\d+)", original)
    if m:
        season = int(m.group(2))

    t = f" {original} "
    for k, v in ROMAN.items():
        t = t.replace(k, v)

    for sw in STOPWORDS:
        t = re.sub(sw, " ", t)

    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()

    words = t.split()
    base = " ".join(words[:6])

    variants = list(dict.fromkeys([
        base,
        " ".join(words),
        base.replace(" ", "")
    ]))

    return {
        "base": base,
        "variants": variants,
        "season": season
    }

# ==================================================
# UTIL
# ==================================================

def get_titles(item):
    titles = [
        item.get("titles", {}).get("english"),
        item.get("titles", {}).get("romaji"),
        item.get("titles", {}).get("native"),
        *item.get("synonyms", [])
    ]
    return list(dict.fromkeys(t for t in titles if t))

# ==================================================
# TMDB HELPERS
# ==================================================

def match_season(tv_id, season_number):
    r = requests.get(
        f"{TMDB_API}/tv/{tv_id}",
        headers=make_headers(),
        timeout=10
    )
    if r.status_code != 200:
        return None

    for season in r.json().get("seasons", []):
        if season.get("season_number") == season_number:
            return {
                "id": tv_id,
                "media_type": "tv",
                "season": season_number,
                "poster": season.get("poster_path"),
                "checked": True
            }
    return None

# ==================================================
# BUSCA TMDB
# ==================================================

def search_tmdb(item):
    for raw_title in get_titles(item):
        norm = normalize_title(raw_title)

        for query in norm["variants"]:
            try:
                r = requests.get(
                    f"{TMDB_API}/search/multi",
                    headers=make_headers(),
                    params={"query": query},
                    timeout=10
                )

                if r.status_code != 200:
                    continue

                for result in r.json().get("results", []):
                    media = result.get("media_type")
                    if media not in ("tv", "movie"):
                        continue

                    date_field = "release_date" if media == "movie" else "first_air_date"
                    year_tmdb = (result.get(date_field) or "")[:4]

                    if item.get("year") and year_tmdb:
                        if abs(int(year_tmdb) - int(item["year"])) > 3:
                            continue

                    if media == "tv" and norm["season"]:
                        season_match = match_season(result["id"], norm["season"])
                        if season_match:
                            return season_match

                    return {
                        "id": result.get("id"),
                        "media_type": media,
                        "poster": result.get("poster_path"),
                        "backdrop": result.get("backdrop_path"),
                        "overview": result.get("overview"),
                        "vote_average": result.get("vote_average"),
                        "release_date": result.get(date_field),
                        "checked": True
                    }

            except Exception:
                continue

    return None

# ==================================================
# ENRICH
# ==================================================

def enrich_one(item):
    if "tmdb" not in item:
        item["tmdb"] = TMDB_EMPTY.copy()

    if item["tmdb"].get("checked"):
        return item

    result = search_tmdb(item)

    if result:
        item["tmdb"] = result
    else:
        item["tmdb"]["checked"] = True

    time.sleep(SLEEP_TIME)
    return item

def enrich_all(data):
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        return list(executor.map(enrich_one, data))

# ==================================================
# MAIN
# ==================================================

if __name__ == "__main__":
    INPUT = "data/anilist.json"
    OUTPUT = "data/anilist_enriched.json"

    with open(INPUT, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"📦 Itens carregados: {len(data)}")

    enriched = enrich_all(data)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(enriched, f, ensure_ascii=False, indent=2)

    found = sum(1 for i in enriched if i["tmdb"].get("id"))
    print(f"✅ TMDB encontrados: {found}")
