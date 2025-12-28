# -*- coding: utf-8 -*-

import os
import re
import json
import time
import unicodedata
import requests
import threading
from itertools import cycle
from concurrent.futures import ThreadPoolExecutor

# ==================================================
# PATHS (à prova de GitHub Actions)
# ==================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INPUT = os.path.join(BASE_DIR, "..", "data", "anilist_raw.json")
OUTPUT = os.path.join(BASE_DIR, "..", "data", "anilist_enriched.json")

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
    raise RuntimeError("❌ Configure 4 TMDB_TOKENs")

token_cycle = cycle(TOKENS)

def headers():
    return {
        "Authorization": f"Bearer {next(token_cycle)}",
        "Content-Type": "application/json;charset=utf-8"
    }

# ==================================================
# CONFIG
# ==================================================

MAX_WORKERS = 4
SLEEP_TIME = 0.12

TMDB_EMPTY = {
    "id": None,
    "media_type": None,
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

# ==================================================
# PROGRESSO (THREAD SAFE)
# ==================================================

lock = threading.Lock()
done = found = not_found = 0
start = time.time()

def log_progress(total):
    elapsed = time.time() - start
    speed = done / elapsed if elapsed else 0
    eta = (total - done) / speed if speed else 0

    print(
        f"[{done:5}/{total}] "
        f"✅ {found} ❌ {not_found} "
        f"{speed:4.2f} it/s ETA {int(eta//60)}m",
        end="\r",
        flush=True
    )

# ==================================================
# NORMALIZAÇÃO
# ==================================================

def clean(txt):
    txt = unicodedata.normalize("NFKD", txt.lower())
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    txt = re.sub(r"[^a-z0-9 ]+", " ", txt)
    return re.sub(r"\s+", " ", txt).strip()

def get_titles(item):
    titles = [
        item.get("titles", {}).get("english"),
        item.get("titles", {}).get("romaji"),
        item.get("titles", {}).get("native"),
        *item.get("synonyms", [])
    ]
    return [t for t in dict.fromkeys(titles) if t]

# ==================================================
# TMDB
# ==================================================

def search(endpoint, query):
    r = requests.get(
        f"{TMDB_API}/search/{endpoint}",
        headers=headers(),
        params={"query": query},
        timeout=10
    )
    return r.json().get("results", []) if r.status_code == 200 else []

def fetch_details(tmdb):
    r = requests.get(
        f"{TMDB_API}/{tmdb['media_type']}/{tmdb['id']}",
        headers=headers(),
        timeout=10
    )
    return r.json() if r.status_code == 200 else {}

def classify(tmdb):
    if tmdb["media_type"] == "movie":
        return "MUSIC" if (tmdb.get("runtime") or 0) < 15 else "MOVIE"

    if tmdb["media_type"] == "tv":
        if (tmdb.get("number_of_episodes") or 0) <= 6:
            return "OVA/ONA"
        if (tmdb.get("episode_run_time") or 0) < 10:
            return "TV_SHORT"
        return "TV"

    return "UNKNOWN"

# ==================================================
# ENRICH
# ==================================================

def enrich_one(item, total):
    global done, found, not_found

    if "tmdb" not in item:
        item["tmdb"] = TMDB_EMPTY.copy()

    if not item["tmdb"]["checked"]:
        for title in get_titles(item):
            query = clean(title)

            for media in ("tv", "movie"):
                for r in search(media, query):
                    tmdb = {
                        "id": r["id"],
                        "media_type": media,
                        "poster": r.get("poster_path"),
                        "backdrop": r.get("backdrop_path"),
                        "overview": r.get("overview"),
                        "vote_average": r.get("vote_average"),
                        "release_date": r.get("first_air_date") or r.get("release_date"),
                        "checked": True,
                        "reason": None
                    }

                    details = fetch_details(tmdb)
                    tmdb["runtime"] = details.get("runtime")
                    tmdb["episode_run_time"] = (
                        details.get("episode_run_time") or [None]
                    )[0]
                    tmdb["number_of_episodes"] = details.get("number_of_episodes")
                    tmdb["tipo_final"] = classify(tmdb)

                    item["tmdb"] = tmdb

                    with lock:
                        found += 1
                    break

                if item["tmdb"]["id"]:
                    break

            if item["tmdb"]["id"]:
                break

        if not item["tmdb"]["id"]:
            item["tmdb"]["checked"] = True
            item["tmdb"]["reason"] = "not_found"
            with lock:
                not_found += 1

    with lock:
        done += 1
        log_progress(total)

    time.sleep(SLEEP_TIME)
    return item

# ==================================================
# MAIN
# ==================================================

if __name__ == "__main__":
    with open(INPUT, "r", encoding="utf-8") as f:
        data = json.load(f)

    total = len(data)
    print(f"📦 Processando {total} animes")

    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        data = list(ex.map(lambda i: enrich_one(i, total), data))

    print("\n💾 Salvando anilist_enriched.json")
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ TMDB encontrados: {found}")
