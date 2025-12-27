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

def make_headers():
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
# PROGRESSO
# ==================================================

progress_lock = threading.Lock()
progress_done = 0
progress_updated = 0
progress_skipped = 0
start_time = time.time()

def log_progress(total):
    elapsed = time.time() - start_time
    speed = progress_done / elapsed if elapsed else 0
    remaining = total - progress_done
    eta = remaining / speed if speed else 0

    def fmt(s):
        return f"{int(s//3600):02}:{int(s%3600//60):02}:{int(s%60):02}"

    percent = (progress_done / total) * 100 if total else 0

    print(
        f"[ {progress_done:5}/{total} | {percent:5.1f}% ] "
        f"🔄 {progress_updated} ⏭ {progress_skipped} | "
        f"{speed:4.2f} it/s | ETA {fmt(eta)}",
        end="\r",
        flush=True
    )

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

def clean_text(txt):
    t = txt.lower()
    for k, v in ROMAN.items():
        t = f" {t} ".replace(k, v)
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c))
    t = re.sub(r"[^a-z0-9 ]+", " ", t)
    return re.sub(r"\s+", " ", t).strip()

def normalize_title(title):
    return clean_text(title)

def safe_first(v):
    return v[0] if isinstance(v, list) and v else None

# ==================================================
# TMDB
# ==================================================

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
        params={"language": "pt-BR"},
        timeout=10
    )

    DETAILS_CACHE[key] = r.json() if r.status_code == 200 else {}
    return DETAILS_CACHE[key]

def classify_tmdb_type(tmdb):
    media = tmdb.get("media_type")
    runtime = tmdb.get("runtime") or 0
    ep_time = tmdb.get("episode_run_time") or 0
    eps = tmdb.get("number_of_episodes") or 0

    if media == "movie":
        return "MUSIC" if runtime and runtime < 15 else "MOVIE"

    if media == "tv":
        if eps and eps <= 6:
            return "OVA/ONA"
        if ep_time and ep_time < 10:
            return "TV_SHORT"
        return "TV"

    return "UNCLASSIFIED"

# ==================================================
# CRITÉRIO DE REPROCESSAMENTO
# ==================================================

def needs_tmdb_update(tmdb):
    return (
        not tmdb.get("id")
        or not tmdb.get("overview")
        or not tmdb.get("poster")
        or not tmdb.get("backdrop")
    )

# ==================================================
# ENRICH
# ==================================================

def enrich_one(item, total):
    global progress_done, progress_updated, progress_skipped

    item.setdefault("tmdb", TMDB_EMPTY.copy())

    if not needs_tmdb_update(item["tmdb"]):
        with progress_lock:
            progress_done += 1
            progress_skipped += 1
            log_progress(total)
        return item

    titles = [
        item.get("titles", {}).get("english"),
        item.get("titles", {}).get("romaji"),
        item.get("titles", {}).get("native"),
        *item.get("synonyms", [])
    ]

    found = None

    for t in filter(None, titles):
        query = normalize_title(t)

        for r in search("tv", query):
            found = r | {"media_type": "tv"}
            break
        if found:
            break

        for r in search("movie", query):
            found = r | {"media_type": "movie"}
            break
        if found:
            break

    if found:
        details = fetch_details(found["media_type"], found["id"])
        item["tmdb"].update({
            "id": found["id"],
            "media_type": found["media_type"],
            "poster": found.get("poster_path"),
            "backdrop": found.get("backdrop_path"),
            "overview": details.get("overview"),
            "vote_average": found.get("vote_average"),
            "release_date": found.get("first_air_date") or found.get("release_date"),
            "runtime": details.get("runtime"),
            "episode_run_time": safe_first(details.get("episode_run_time")),
            "number_of_episodes": details.get("number_of_episodes"),
            "checked": True,
            "reason": None
        })
        item["tmdb"]["tipo_final"] = classify_tmdb_type(item["tmdb"])

        with progress_lock:
            progress_updated += 1
    else:
        item["tmdb"]["checked"] = True
        item["tmdb"]["reason"] = "not_found"

    with progress_lock:
        progress_done += 1
        log_progress(total)

    time.sleep(SLEEP_TIME)
    return item

def enrich_all(data):
    total = len(data)
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        return list(ex.map(lambda i: enrich_one(i, total), data))

# ==================================================
# MAIN
# ==================================================

if __name__ == "__main__":
    PATH = "data/anilist_enriched.json"

    with open(PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"📦 Itens carregados: {len(data)}")

    enriched = enrich_all(data)
    print()

    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(enriched, f, ensure_ascii=False, indent=2)

    print("✅ Atualização incremental concluída")
