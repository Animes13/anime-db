# -*- coding: utf-8 -*-

import os
import re
import json
import time
import unicodedata
import requests
from itertools import cycle
from concurrent.futures import ThreadPoolExecutor, as_completed

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
SLEEP_TIME = 0.12
YEAR_TOLERANCE = 6

TMDB_EMPTY = {
    "id": None,
    "media_type": None,
    "season": None,
    "poster": None,
    "backdrop": None,
    "overview": None,
    "vote_average": None,
    "release_date": None,
    "runtime": None,
    "episode_run_time": None,
    "number_of_episodes": None,
    "tipo_final": None,
    "checked": False,
    "reason": None
}

DETAILS_CACHE = {}

# ==================================================
# NORMALIZAÇÃO
# ==================================================

ROMAN = {
    " i ": " 1 ",
    " ii ": " 2 ",
    " iii ": " 3 ",
    " iv ": " 4 ",
    " v ": " 5 ",
    " vi ": " 6 ",
}

SOFT_STOPWORDS = [
    r"\b(tv|the animation|anime)\b",
]

SEASON_RE = re.compile(r"(season|stage|part|cour)\s*(\d+)", re.I)

def clean_text(txt: str):
    t = txt.lower()
    for k, v in ROMAN.items():
        t = f" {t} ".replace(k, v)

    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t

def normalize_title(title: str):
    season = None
    m = SEASON_RE.search(title)
    if m:
        season = int(m.group(2))

    raw = clean_text(title)

    soft = raw
    for sw in SOFT_STOPWORDS:
        soft = re.sub(sw, " ", soft)
    soft = re.sub(r"\s+", " ", soft).strip()

    return {
        "raw": raw,
        "soft": soft,
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

def search_endpoint(endpoint, query):
    r = requests.get(
        f"{TMDB_API}/search/{endpoint}",
        headers=make_headers(),
        params={"query": query},
        timeout=10
    )
    if r.status_code != 200:
        return []
    return r.json().get("results", [])

def year_ok(item_year, tmdb_year):
    if not item_year or not tmdb_year:
        return True
    return abs(int(tmdb_year) - int(item_year)) <= YEAR_TOLERANCE

def match_season(tv_id, wanted):
    r = requests.get(
        f"{TMDB_API}/tv/{tv_id}",
        headers=make_headers(),
        timeout=10
    )
    if r.status_code != 200:
        return None

    seasons = r.json().get("seasons", [])
    for s in seasons:
        if s.get("season_number") == wanted:
            return wanted
    for s in seasons:
        if s.get("season_number") == 0:
            return 0
    return None

def build_tmdb(result, media, season=None):
    date_field = "release_date" if media == "movie" else "first_air_date"
    return {
        "id": result.get("id"),
        "media_type": media,
        "season": season,
        "poster": result.get("poster_path"),
        "backdrop": result.get("backdrop_path"),
        "overview": result.get("overview"),
        "vote_average": result.get("vote_average"),
        "release_date": result.get(date_field),
        "checked": True,
        "reason": None
    }

def fetch_tmdb_details(tmdb):
    media = tmdb.get("media_type")
    tmdb_id = tmdb.get("id")
    if not media or not tmdb_id:
        return {}

    key = f"{media}:{tmdb_id}"
    if key in DETAILS_CACHE:
        return DETAILS_CACHE[key]

    r = requests.get(
        f"{TMDB_API}/{media}/{tmdb_id}",
        headers=make_headers(),
        timeout=10
    )
    if r.status_code != 200:
        DETAILS_CACHE[key] = {}
        return {}

    DETAILS_CACHE[key] = r.json()
    return DETAILS_CACHE[key]

# ==================================================
# CLASSIFICAÇÃO
# ==================================================

def classify_tmdb_type(tmdb):
    media = tmdb.get("media_type")
    runtime = tmdb.get("runtime")
    ep_time = tmdb.get("episode_run_time")
    eps = tmdb.get("number_of_episodes")

    if media == "movie":
        if runtime and runtime < 15:
            return "MUSIC"
        return "MOVIE"

    if media == "tv":
        if eps and eps <= 6:
            return "OVA/ONA"
        if ep_time and ep_time < 10:
            return "TV_SHORT"
        return "TV"

    return "UNCLASSIFIED"

# ==================================================
# BUSCA TMDB
# ==================================================

def search_tmdb(item):
    for title in get_titles(item):
        norm = normalize_title(title)
        for query in (norm["raw"], norm["soft"]):

            for r in search_endpoint("tv", query):
                year = (r.get("first_air_date") or "")[:4]
                if not year_ok(item.get("year"), year):
                    continue
                season = None
                if norm["season"] is not None:
                    season = match_season(r["id"], norm["season"])
                    if season is None:
                        continue
                return build_tmdb(r, "tv", season)

            for r in search_endpoint("movie", query):
                year = (r.get("release_date") or "")[:4]
                if not year_ok(item.get("year"), year):
                    continue
                return build_tmdb(r, "movie")

            for r in search_endpoint("multi", query):
                media = r.get("media_type")
                if media not in ("tv", "movie"):
                    continue
                year = (
                    (r.get("first_air_date") or "")[:4]
                    if media == "tv"
                    else (r.get("release_date") or "")[:4]
                )
                if not year_ok(item.get("year"), year):
                    continue
                return build_tmdb(r, media)

    return None

# ==================================================
# ENRICH
# ==================================================

def enrich_one(idx, item, total):
    if "tmdb" not in item:
        item["tmdb"] = TMDB_EMPTY.copy()

    if item["tmdb"].get("checked"):
        return item

    result = search_tmdb(item)

    if result:
        details = fetch_tmdb_details(result)

        result["runtime"] = details.get("runtime")
        result["episode_run_time"] = (
            details.get("episode_run_time", [None])[0]
            if isinstance(details.get("episode_run_time"), list)
            else details.get("episode_run_time")
        )
        result["number_of_episodes"] = details.get("number_of_episodes")
        result["tipo_final"] = classify_tmdb_type(result)

        item["tmdb"] = result
        print(f"[{idx}/{total}] ✅ TMDB ({result['tipo_final']})")
    else:
        item["tmdb"].update({
            "checked": True,
            "reason": "not_found"
        })
        print(f"[{idx}/{total}] ❌ Sem TMDB")

    time.sleep(SLEEP_TIME)
    return item

def enrich_all(data):
    total = len(data)
    results = [None] * total

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {
            executor.submit(enrich_one, i + 1, data[i], total): i
            for i in range(total)
        }
        for f in as_completed(futures):
            results[futures[f]] = f.result()

    return results

# ==================================================
# MAIN
# ==================================================

if __name__ == "__main__":
    INPUT = "data/anilist_raw.json"
    OUTPUT = "data/anilist_enriched.json"

    with open(INPUT, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"📦 Itens carregados: {len(data)}")

    enriched = enrich_all(data)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(enriched, f, ensure_ascii=False, indent=2)

    found = sum(1 for i in enriched if i["tmdb"].get("id"))
    print(f"✅ TMDB encontrados: {found}")
