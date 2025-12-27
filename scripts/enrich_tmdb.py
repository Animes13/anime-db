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

# ==================================================
# PROGRESSO
# ==================================================

lock = threading.Lock()
done = found = not_found = 0
start = time.time()

def log_progress(total):
    elapsed = time.time() - start
    speed = done / elapsed if elapsed else 0
    eta = (total - done) / speed if speed else 0

    print(
        f"[{done}/{total}] "
        f"✅ {found} ❌ {not_found} "
        f"{speed:.2f} it/s ETA {int(eta//60)}m",
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

def enrich_one(item, total):
    global done, found, not_found

    if "tmdb" not in item:
        item["tmdb"] = TMDB_EMPTY.copy()

    if not item["tmdb"]["checked"]:
        for title in get_titles(item):
            query = clean(title)

            for r in search("tv", query):
                item["tmdb"].update({
                    "id": r["id"],
                    "media_type": "tv",
                    "checked": True
                })
                found += 1
                break

            if item["tmdb"]["id"]:
                break

            for r in search("movie", query):
                item["tmdb"].update({
                    "id": r["id"],
                    "media_type": "movie",
                    "checked": True
                })
                found += 1
                break

        if not item["tmdb"]["id"]:
            item["tmdb"]["checked"] = True
            item["tmdb"]["reason"] = "not_found"
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
    with open("anilist_raw.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    total = len(data)
    print(f"📦 Processando {total} animes")

    with ThreadPoolExecutor(MAX_WORKERS) as ex:
        data = list(ex.map(lambda i: enrich_one(i, total), data))

    print("\n💾 Salvando anilist_enriched.json")
    with open("anilist_enriched.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
