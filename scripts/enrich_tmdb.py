# -*- coding: utf-8 -*-

import os
import re
import json
import time
import unicodedata
import requests
import threading
import subprocess
from itertools import cycle
from concurrent.futures import ThreadPoolExecutor

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

def make_headers():
    return {
        "Authorization": f"Bearer {next(token_cycle)}",
        "Content-Type": "application/json;charset=utf-8"
    }

MAX_WORKERS = 4
SLEEP_TIME = 0.12

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

lock = threading.Lock()
done = found = not_found = 0
start = time.time()

def log_progress(total):
    elapsed = time.time() - start
    speed = done / elapsed if elapsed else 0
    eta = (total - done) / speed if speed else 0
    print(
        f"[ {done:5}/{total} ] ✅ {found} ❌ {not_found} "
        f"{speed:4.2f} it/s ETA {int(eta//60)}m",
        end="\r",
        flush=True
    )

def clean(txt):
    txt = unicodedata.normalize("NFKD", txt.lower())
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    txt = re.sub(r"[^a-z0-9 ]+", " ", txt)
    return re.sub(r"\s+", " ", txt).strip()

def get_titles(item):
    return [
        t for t in [
            item.get("titles", {}).get("english"),
            item.get("titles", {}).get("romaji"),
            item.get("titles", {}).get("native"),
            *item.get("synonyms", [])
        ] if t
    ]

def search(endpoint, query):
    r = requests.get(
        f"{TMDB_API}/search/{endpoint}",
        headers=make_headers(),
        params={"query": query},
        timeout=10
    )
    return r.json().get("results", []) if r.status_code == 200 else []

def fetch_details(media, tmdb_id):
    key = f"{media}:{tmdb_id}"
    if key in DETAILS_CACHE:
        return DETAILS_CACHE[key]

    r = requests.get(
        f"{TMDB_API}/{media}/{tmdb_id}",
        headers=make_headers(),
        timeout=10
    )
    DETAILS_CACHE[key] = r.json() if r.status_code == 200 else {}
    return DETAILS_CACHE[key]

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

    item.setdefault("tmdb", {})
    for k, v in TMDB_EMPTY.items():
        item["tmdb"].setdefault(k, v)

    tmdb = item["tmdb"]

    # 🔥 só pula se estiver COMPLETO
    if tmdb["checked"] and tmdb["id"] and tmdb.get("overview"):
        with lock:
            done += 1
            log_progress(total)
        return item

    match = None

    for title in get_titles(item):
        q = clean(title)

        for r in search("tv", q):
            match = {"id": r["id"], "media_type": "tv"}
            break
        if match:
            break

        for r in search("movie", q):
            match = {"id": r["id"], "media_type": "movie"}
            break
        if match:
            break

    if match:
        d = fetch_details(match["media_type"], match["id"])
        match.update({
            "season": None,
            "poster": d.get("poster_path"),
            "backdrop": d.get("backdrop_path"),
            "overview": d.get("overview"),
            "vote_average": d.get("vote_average"),
            "release_date": d.get("first_air_date") or d.get("release_date"),
            "runtime": d.get("runtime"),
            "episode_run_time": (d.get("episode_run_time") or [None])[0],
            "number_of_episodes": d.get("number_of_episodes"),
            "checked": True,
            "reason": None
        })
        match["tipo_final"] = classify(match)
        item["tmdb"] = match
        found += 1
    else:
        tmdb["checked"] = True
        tmdb["reason"] = "not_found_enrich"
        not_found += 1

    with lock:
        done += 1
        log_progress(total)

    time.sleep(SLEEP_TIME)
    return item

if __name__ == "__main__":
    INPUT = "data/anilist_raw.json"
    OUTPUT = "data/anilist_enriched.json"

    with open(INPUT, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"📦 Processando {len(data)} animes")

    with ThreadPoolExecutor(MAX_WORKERS) as ex:
        data = list(ex.map(lambda i: enrich_one(i, len(data)), data))

    print("\n💾 Salvando anilist_enriched.json")
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("🔁 Executando segunda chance...")
    subprocess.run(["python", "scripts/retry_tmdb_missing.py"], check=True)