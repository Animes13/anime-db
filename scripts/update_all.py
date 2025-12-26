import json
from datetime import datetime

INPUT_FILE = "data/anilist_enriched.json"

with open(INPUT_FILE, encoding="utf-8") as f:
    items = json.load(f)

tv = []
movies = []
index = {}

VALID_FORMATS = {"TV", "MOVIE"}

for a in items:
    fmt = a.get("format")
    if fmt not in VALID_FORMATS:
        continue

    entry = {
        "anilist_id": a.get("anilist_id"),
        "titles": a.get("titles", {}),
        "synonyms": a.get("synonyms", []),
        "genres": a.get("genres", []),
        "episodes": a.get("episodes"),
        "year": a.get("year"),
        "status": a.get("status"),
        "tmdb": a.get("tmdb", {})
    }

    if fmt == "MOVIE":
        movies.append(entry)
        index[str(entry["anilist_id"])] = "movie"
    else:
        tv.append(entry)
        index[str(entry["anilist_id"])] = "tv"

# 🔽 Escrita dos arquivos finais
with open("data/anime_tv.json", "w", encoding="utf-8") as f:
    json.dump(tv, f, ensure_ascii=False, indent=2)

with open("data/anime_movies.json", "w", encoding="utf-8") as f:
    json.dump(movies, f, ensure_ascii=False, indent=2)

with open("data/index.json", "w", encoding="utf-8") as f:
    json.dump(index, f, ensure_ascii=False, indent=2)

meta = {
    "source": "AniList + TMDB",
    "last_update": datetime.utcnow().isoformat() + "Z",
    "total": len(tv) + len(movies),
    "tv_count": len(tv),
    "movie_count": len(movies)
}

with open("data/meta.json", "w", encoding="utf-8") as f:
    json.dump(meta, f, ensure_ascii=False, indent=2)

print("✅ Banco atualizado com sucesso")
print(f"📺 TV: {len(tv)} | 🎬 Movies: {len(movies)}")
