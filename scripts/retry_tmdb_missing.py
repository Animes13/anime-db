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
MIN_OVERVIEW_LEN = 20

# ==================================================
# PROGRESSO
# ==================================================

lock = threading.Lock()
done = fixed = failed = 0
start = time.time()

def log_progress(total):
    elapsed = time.time() - start
    speed = done / elapsed if elapsed else 0
    eta = (total - done) / speed if speed else 0

    print(
        f"[ {done:5}/{total} ] "
        f"🔧 {fixed} ⚠️ {failed} "
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
# REGRAS DE RETRY
# ==================================================

def needs_retry(item):
    tmdb = item.get("tmdb") or {}

    if not tmdb.get("id"):
        return True

    overview = tmdb.get("overview")
    if not overview or len(overview.strip()) < MIN_OVERVIEW_LEN:
        return True

    return False

# ==================================================
# TMDB HELPERS
# ==================================================

def search(endpoint, query):
    r = requests.get(
        f"{TMDB_API}/search/{endpoint}",
        headers=headers(),
        params={"query": query},
        timeout=10
    )
    return r.json().get("results", []) if r.status_code == 200 else []

def fetch_details(media, tmdb_id):
    # PT-BR primeiro
    r = requests.get(
        f"{TMDB_API}/{media}/{tmdb_id}",
        headers=headers(),
        params={"language": "pt-BR"},
        timeout=10
    )
    data = r.json() if r.status_code == 200 else {}

    # fallback EN-US
    if not data.get("overview"):
        r = requests.get(
            f"{TMDB_API}/{media}/{tmdb_id}",
            headers=headers(),
            params={"language": "en-US"},
            timeout=10
        )
        data = r.json() if r.status_code == 200 else {}

    return data

# ==================================================
# RETRY
# ==================================================

def retry_one(item, total):
    global done, fixed, failed

    tmdb = item.get("tmdb") or {}
    success = False

    # Caso já tenha ID → só atualizar detalhes
    if tmdb.get("id"):
        details = fetch_details(tmdb["media_type"], tmdb["id"])
        if details.get("overview"):
            tmdb.update({
                "overview": details.get("overview"),
                "poster": details.get("poster_path"),
                "backdrop": details.get("backdrop_path"),
                "vote_average": details.get("vote_average"),
                "release_date": details.get("release_date") or details.get("first_air_date"),
            })
            success = True

    # Caso não tenha ID → tentar nova busca
    else:
        for title in get_titles(item):
            query = clean(title)

            for media in ("tv", "movie"):
                for r in search(media, query):
                    details = fetch_details(media, r["id"])
                    if details.get("overview"):
                        item["tmdb"] = {
                            "id": r["id"],
                            "media_type": media,
                            "season": None,
                            "poster": details.get("poster_path"),
                            "backdrop": details.get("backdrop_path"),
                            "overview": details.get("overview"),
                            "vote_average": details.get("vote_average"),
                            "release_date": details.get("release_date") or details.get("first_air_date"),
                            "checked": True,
                            "reason": None,
                        }
                        success = True
                        break
                if success:
                    break
            if success:
                break

    with lock:
        done += 1
        if success:
            fixed += 1
        else:
            failed += 1
        log_progress(total)

    time.sleep(SLEEP_TIME)
    return item

# ==================================================
# MAIN
# ==================================================

if __name__ == "__main__":
    BASE = os.path.dirname(os.path.abspath(__file__))
    INPUT = os.path.join(BASE, "..", "data", "anilist_enriched.json")
    OUTPUT = os.path.join(BASE, "..", "data", "anilist_enriched_final.json")

    with open(INPUT, "r", encoding="utf-8") as f:
        data = json.load(f)

    retry_items = [i for i in data if needs_retry(i)]
    total = len(retry_items)

    print(f"🔁 Segunda chance: {total} itens")

    retry_map = {}

    with ThreadPoolExecutor(MAX_WORKERS) as ex:
        for item in ex.map(lambda i: retry_one(i, total), retry_items):
            retry_map[item["anilist_id"]] = item

    # merge final
    for i, item in enumerate(data):
        if item["anilist_id"] in retry_map:
            data[i] = retry_map[item["anilist_id"]]

    print("\n💾 Salvando anilist_enriched_final.json")
    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"✅ Corrigidos: {fixed} | ⚠️ Ainda problemáticos: {failed}")
