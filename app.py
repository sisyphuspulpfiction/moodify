"""
Moodify - Spotify Mood Playlist Creator
Flask backend
Made By Claude and Gürol :)
"""

from flask import Flask, redirect, request, session, jsonify, render_template
from flask_cors import CORS
import requests
import os
import time
import urllib.parse
import json

app = Flask(__name__)
app.secret_key = os.urandom(24)
CORS(app)

# ─── CONFIG ──────────────────────────────────────────────────────────────────
CLIENT_ID     = os.environ.get("SPOTIFY_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("SPOTIFY_CLIENT_SECRET", "")
REDIRECT_URI  = "http://127.0.0.1:5000/callback"
SCOPE         = "playlist-modify-public playlist-modify-private user-library-read"

AUTH_URL    = "https://accounts.spotify.com/authorize"
TOKEN_URL   = "https://accounts.spotify.com/api/token"
API_BASE    = "https://api.spotify.com/v1"

MOOD_EMOJIS = {
    "Hype / Party":               "🎉",
    "Pump-Up / Workout":          "💪",
    "Dark & Intense":             "🌑",
    "Feel-Good / Upbeat":         "😄",
    "Cruising / Everyday":        "🚗",
    "Melancholic / Moody":        "😔",
    "Sunny / Laid-Back":          "☀️",
    "Acoustic / Soulful":         "🎸",
    "Calm Acoustic":              "🎵",
    "Energetic Instrumental":     "⚡",
    "Ambient / Chill Instrumental":"🌙",
    "Relaxed / Mellow":           "😌",
    "Sad / Reflective":           "💧",
}

# ─── CLASSIFICATION SYSTEM 2.0 ──────────────────────────────────────────────

GENRE_MAP = {
    "ambient":        {"energy": 0, "tone": "NEUTRAL", "context": "SLEEP",     "sonic": ["INSTRUMENTAL", "LO_FI"]},
    "meditation":      {"energy": 0, "tone": "TENDER",  "context": "SLEEP",     "sonic": ["INSTRUMENTAL"]},
    "lo-fi":          {"energy": 1, "tone": "NEUTRAL", "context": "FOCUS",     "sonic": ["LO_FI", "INSTRUMENTAL"]},
    "classical":      {"energy": 1, "tone": "TENDER",  "context": "FOCUS",     "sonic": ["ORCHESTRAL", "ACOUSTIC"]},
    "jazz":           {"energy": 2, "tone": "NEUTRAL", "context": "SOCIAL",    "sonic": ["LIVE_FEEL", "ACOUSTIC"]},
    "bossa nova":     {"energy": 1, "tone": "JOYFUL",  "context": "DRIVING",   "sonic": ["ACOUSTIC"]},
    "folk":           {"energy": 2, "tone": "TENDER",  "context": "NOSTALGIA", "sonic": ["ACOUSTIC", "VOCAL_HEAVY"]},
    "singer-songwriter": {"energy": 2, "tone": "SAD",     "context": "HEARTBREAK","sonic": ["ACOUSTIC", "VOCAL_HEAVY"]},
    "indie rock":     {"energy": 3, "tone": "NEUTRAL", "context": "DRIVING",   "sonic": ["LIVE_FEEL", "RAW"]},
    "alternative":     {"energy": 3, "tone": "DARK",    "context": "LATE_NIGHT","sonic": ["RAW"]},
    "pop":            {"energy": 3, "tone": "JOYFUL",  "context": "SOCIAL",    "sonic": ["PRODUCED"]},
    "dance pop":      {"energy": 4, "tone": "EUPHORIC", "context": "SOCIAL",    "sonic": ["ELECTRONIC", "PRODUCED"]},
    "edm":            {"energy": 4, "tone": "EUPHORIC", "context": "WORKOUT",   "sonic": ["ELECTRONIC"]},
    "techno":         {"energy": 4, "tone": "DARK",    "context": "LATE_NIGHT","sonic": ["ELECTRONIC", "INSTRUMENTAL"]},
    "metal":          {"energy": 4, "tone": "DARK",    "context": "WORKOUT",   "sonic": ["RAW", "LIVE_FEEL"]},
    "punk":           {"energy": 4, "tone": "DARK",    "context": "WORKOUT",   "sonic": ["RAW"]},
    "hip hop":        {"energy": 3, "tone": "NEUTRAL", "context": "SOCIAL",    "sonic": ["PRODUCED"]},
    "rap":            {"energy": 3, "tone": "DARK",    "context": "WORKOUT",   "sonic": ["VOCAL_HEAVY"]},
    "r&b":            {"energy": 2, "tone": "TENDER",  "context": "LATE_NIGHT","sonic": ["VOCAL_HEAVY", "PRODUCED"]},
    "soul":           {"energy": 2, "tone": "JOYFUL",  "context": "NOSTALGIA", "sonic": ["VOCAL_HEAVY", "ACOUSTIC"]},
    "reggae":         {"energy": 2, "tone": "JOYFUL",  "context": "ADVENTURE", "sonic": ["LIVE_FEEL"]},
    "shoegaze":       {"energy": 2, "tone": "DARK",    "context": "LATE_NIGHT","sonic": ["CINEMATIC", "RAW"]},
}

NLP_SIGNALS = {
    "DARK":       ["night", "dark", "death", "blood", "void", "shadow", "kill", "devil", "hell", "burn"],
    "SAD":        ["cry", "tears", "goodbye", "alone", "broken", "miss", "hurt", "lost", "empty", "never"],
    "JOYFUL":     ["sunshine", "happy", "good time", "party", "dance", "celebrate", "love", "summer", "free"],
    "TENDER":     ["hold", "close", "soft", "dream", "gentle", "together", "home", "heart"],
    "EUPHORIC":   ["sky", "star", "light", "higher", "fly", "heaven", "magic"],
    "LATE_NIGHT": ["midnight", "3am", "late", "insomnia", "moonlight", "after dark"],
    "WORKOUT":    ["power", "beast", "fire", "run", "grind", "hustle", "stronger"],
}

OVERRIDE_ARTISTS = {
    "Radiohead": {"tone": "DARK", "context": "LATE_NIGHT"},
    "Lana Del Rey": {"tone": "SAD", "context": "NOSTALGIA"},
    "Metallica": {"energy": 4, "context": "WORKOUT"},
    "Enya": {"energy": 0, "context": "SLEEP"},
}

def classify_track(track):
    """Moodify 2.0 Multi-dimensional Scoring System"""
    name   = track.get("name", "").lower()
    album  = track.get("album", "").lower()
    genres = track.get("genres", [])
    artist = track.get("artist", "").split(",")[0].strip()
    year   = track.get("release_year", 2020)

    # Era Dimension (Fixed)
    if year < 1980:   era = "PRE_80s"
    elif year < 1990: era = "80s"
    elif year < 2000: era = "90s"
    elif year < 2010: era = "00s"
    elif year < 2020: era = "10s"
    else:             era = "20s"

    # Default Scores
    scores = {
        "energy":  [2], # Default Moderate
        "tone":    {"DARK":0, "SAD":0, "NEUTRAL":1, "TENDER":0, "HOPEFUL":0, "JOYFUL":0, "EUPHORIC":0},
        "context": {"FOCUS":0, "DRIVING":1, "WORKOUT":0, "SOCIAL":0, "SLEEP":0, "HEARTBREAK":0, "NOSTALGIA":0, "ADVENTURE":0, "LATE_NIGHT":0},
        "sonic":   []
    }

    # Weighting: Genre
    for g in genres:
        for kw, val in GENRE_MAP.items():
            if kw in g:
                scores["energy"].append(val["energy"])
                scores["tone"][val["tone"]] += 3
                scores["context"][val["context"]] += 3
                scores["sonic"].extend(val.get("sonic", []))

    # Weighting: NLP Name/Album (30%)
    meta_str = f"{name} {album}"
    for tone, signals in NLP_SIGNALS.items():
        if any(s in meta_str for s in signals):
            if tone in scores["tone"]: scores["tone"][tone] += 3
            if tone in scores["context"]: scores["context"][tone] += 3
            if tone == "WORKOUT": scores["energy"].append(4)

    # Weighting: Artist Overrides (10%)
    if artist in OVERRIDE_ARTISTS:
        ov = OVERRIDE_ARTISTS[artist]
        if "energy" in ov: scores["energy"].append(ov["energy"])
        if "tone" in ov: scores["tone"][ov["tone"]] += 5
        if "context" in ov: scores["context"][ov["context"]] += 5

    # Era Impact on Nostalgia
    if era in ["PRE_80s", "80s", "90s"]:
        scores["context"]["NOSTALGIA"] += 2

    # Resolve Dimensions
    # prioritize highest energy signal if high, else average
    if any(e >= 4 for e in scores["energy"]): energy = 4
    elif any(e >= 3 for e in scores["energy"]): energy = 3
    else: energy = int(sum(scores["energy"]) / len(scores["energy"]))

    tone = max(scores["tone"], key=scores["tone"].get)
    context = max(scores["context"], key=scores["context"].get)

    # Sonic tags (Top 3 unique)
    sonic = sorted(list(set(scores["sonic"])), key=lambda x: scores["sonic"].count(x), reverse=True)[:3]
    if not sonic: sonic = ["PRODUCED"]

    return {
        "energy":  energy,
        "tone":    tone,
        "context": context,
        "sonic":   sonic,
        "era":     era
    }

# ─── HELPERS ─────────────────────────────────────────────────────────────────
def api_get(path, token, params=None):
    r = requests.get(f"{API_BASE}{path}",
                     headers={"Authorization": f"Bearer {token}"},
                     params=params)
    r.raise_for_status()
    return r.json()

def api_post(path, token, payload):
    r = requests.post(f"{API_BASE}{path}",
                      headers={"Authorization": f"Bearer {token}",
                               "Content-Type": "application/json"},
                      json=payload)
    r.raise_for_status()
    return r.json()

def refresh_token_if_needed():
    if "access_token" not in session:
        return False
    if time.time() > session.get("expires_at", 0):
        r = requests.post(TOKEN_URL, data={
            "grant_type":    "refresh_token",
            "refresh_token": session["refresh_token"],
            "client_id":     CLIENT_ID,
            "client_secret": CLIENT_SECRET,
        })
        data = r.json()
        session["access_token"] = data["access_token"]
        session["expires_at"]   = time.time() + data["expires_in"]
    return True

def chunk(lst, size):
    for i in range(0, len(lst), size):
        yield lst[i:i + size]

# ─── ROUTES ──────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html",
                           logged_in="access_token" in session,
                           client_id=CLIENT_ID)

@app.route("/login")
def login():
    params = {
        "client_id":     CLIENT_ID,
        "response_type": "code",
        "redirect_uri":  REDIRECT_URI,
        "scope":         SCOPE,
    }
    return redirect(f"{AUTH_URL}?{urllib.parse.urlencode(params)}")

@app.route("/callback")
def callback():
    code = request.args.get("code")
    r = requests.post(TOKEN_URL, data={
        "grant_type":   "authorization_code",
        "code":         code,
        "redirect_uri": REDIRECT_URI,
        "client_id":    CLIENT_ID,
        "client_secret":CLIENT_SECRET,
    })
    data = r.json()
    session["access_token"]  = data["access_token"]
    session["refresh_token"] = data["refresh_token"]
    session["expires_at"]    = time.time() + data["expires_in"]
    return redirect("/")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")

@app.route("/api/me")
def me():
    if not refresh_token_if_needed():
        return jsonify({"error": "not logged in"}), 401
    user = api_get("/me", session["access_token"])
    images = user.get("images", [])
    image_url = images[0].get("url", "") if images else ""
    return jsonify({"name": user.get("display_name", user["id"]),
                    "id":   user["id"],
                    "image": image_url})

# ─── PLAYLIST RECIPES ────────────────────────────────────────────────────────

PLAYLIST_RECIPES = [
    {"id": "3am_drive",      "name": "3am Drive",          "emoji": "🌃", "req": {"context": "LATE_NIGHT", "energy": [2,3], "tone": ["DARK", "NEUTRAL"]}},
    {"id": "gym_beast",      "name": "Gym Beast Mode",     "emoji": "🔥", "req": {"context": "WORKOUT",    "energy": [4],   "tone": ["DARK", "EUPHORIC"]}},
    {"id": "sunday_morning", "name": "Sunday Morning",      "emoji": "☕", "req": {"energy": [0,1],       "tone": ["TENDER"], "sonic": ["ACOUSTIC"]}},
    {"id": "broken_heart",   "name": "Broken Heart at 2am","emoji": "💔", "req": {"context": "HEARTBREAK", "tone": ["SAD"]}},
    {"id": "pre_game",       "name": "Pre-Game Hype",      "emoji": "🥂", "req": {"context": "SOCIAL",     "energy": [3,4], "tone": ["EUPHORIC"]}},
    {"id": "deep_focus",     "name": "Deep Focus",         "emoji": "🧠", "req": {"context": "FOCUS",      "energy": [1,2], "sonic": ["INSTRUMENTAL", "LO_FI"]}},
    {"id": "road_trip",      "name": "Road Trip Anthems",  "emoji": "🚗", "req": {"context": "ADVENTURE",  "energy": [3,4], "tone": ["HOPEFUL", "JOYFUL", "EUPHORIC"]}},
    {"id": "rainy_day",      "name": "Rainy Day Indie",    "emoji": "🌧️", "req": {"energy": [1,2],       "tone": ["SAD", "NEUTRAL"], "sonic": ["LIVE_FEEL", "ACOUSTIC"]}},
    {"id": "club_ready",     "name": "Club Ready",         "emoji": "💃", "req": {"context": "SOCIAL",     "energy": [4],   "sonic": ["ELECTRONIC"]}},
    {"id": "nostalgia_90s",  "name": "90s Nostalgia",      "emoji": "📼", "req": {"era": ["90s"]}},
    {"id": "nostalgia_80s",  "name": "80s Nostalgia",      "emoji": "🕹️", "req": {"era": ["80s"]}},
    {"id": "nostalgia_00s",  "name": "00s Nostalgia",      "emoji": "🎧", "req": {"era": ["00s"]}},
]

@app.route("/api/analyze")
def analyze():
    if not refresh_token_if_needed():
        return jsonify({"error": "not logged in"}), 401

    token = session["access_token"]
    tracks = []
    artist_genres = {}

    # 0. Bootstrap genres from top artists (1 call, 50 artists)
    try:
        top_artists = api_get("/me/top/artists", token, {"limit": 50})
        for a in top_artists.get("items", []):
            artist_genres[a["id"]] = a.get("genres", [])
    except: pass

    # 1. Fetch Liked Songs
    url = "/me/tracks"
    params = {"limit": 50, "offset": 0}
    while True:
        data = api_get(url, token, params)
        for item in data.get("items", []):
            t = item["track"]
            if not t: continue
            tracks.append({
                "uri":    t["uri"],
                "name":   t["name"],
                "artist": ", ".join(a["name"] for a in t["artists"]),
                "artist_ids": [a["id"] for a in t["artists"]],
                "album":  t["album"]["name"],
                "image":  t["album"]["images"][0]["url"] if t.get("album", {}).get("images") else "",
                "release_year": int(t["album"]["release_date"].split("-")[0]) if t.get("album", {}).get("release_date") else 2020
            })
        if not data.get("next"): break
        params["offset"] += 50
        time.sleep(0.05)

    # 2. Fetch Artist Metadata (Genres) with Cache
    cache_file = "artist_cache.json"
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r") as f:
                cached = json.load(f)
                artist_genres.update(cached)
        except: pass

    all_artist_ids = list(set(aid for t in tracks for aid in t["artist_ids"]))
    to_fetch = [aid for aid in all_artist_ids if aid not in artist_genres]

    if to_fetch:
        for batch in chunk(to_fetch, 50):
            try:
                r = requests.get(f"{API_BASE}/artists", headers={"Authorization": f"Bearer {token}"}, params={"ids": ",".join(batch)})
                if r.status_code == 200:
                    for a in r.json().get("artists", []):
                        if a: artist_genres[a["id"]] = a.get("genres", [])
                elif r.status_code == 429:
                    wait = int(r.headers.get("Retry-After", 5))
                    time.sleep(wait)
            except: pass
            time.sleep(0.1)

        with open(cache_file, "w") as f:
            json.dump(artist_genres, f)

    # 3. Classify Tracks
    classified_tracks = []
    for t in tracks:
        t["genres"] = []
        for aid in t["artist_ids"]:
            t["genres"].extend(artist_genres.get(aid, []))
        t["genres"] = list(set(t["genres"]))

        t["profile"] = classify_track(t)
        classified_tracks.append(t)

    # 4. Generate Playlists from Recipes
    generated_playlists = []
    for recipe in PLAYLIST_RECIPES:
        match_uris = []
        match_arts = []
        match_artists = []

        for t in classified_tracks:
            p = t["profile"]
            req = recipe["req"]

            is_match = True
            if "context" in req and p["context"] != req["context"]: is_match = False
            if "energy" in req and p["energy"] not in req["energy"]: is_match = False
            if "tone" in req and p["tone"] not in req["tone"]: is_match = False
            if "era" in req and p["era"] not in req["era"]: is_match = False
            if "sonic" in req and not any(s in p["sonic"] for s in req["sonic"]): is_match = False

            if is_match:
                match_uris.append(t["uri"])
                if t["image"] and len(match_arts) < 4: match_arts.append(t["image"])
                if len(match_artists) < 10: match_artists.append(t.get("artist", "").split(",")[0])

        if len(match_uris) >= 15:
            # Handle Volumes (split every 60 tracks)
            vols = list(chunk(match_uris, 60))
            for i, vol_uris in enumerate(vols):
                name = recipe["name"]
                if len(vols) > 1: name += f" Vol. {i+1}"

                generated_playlists.append({
                    "id": f"{recipe['id']}_{i}",
                    "name": name,
                    "emoji": recipe["emoji"],
                    "track_count": len(vol_uris),
                    "top_artists": sorted(list(set(match_artists)), key=lambda x: match_artists.count(x), reverse=True)[:3],
                    "album_arts": match_arts,
                    "energy_level": recipe["req"].get("energy", [2])[0],
                    "tone": recipe["req"].get("tone", ["NEUTRAL"])[0],
                    "context": recipe["req"].get("context", "DRIVING"),
                    "uris": vol_uris
                })

    return jsonify({
        "total": len(tracks),
        "playlists": generated_playlists
    })

@app.route("/api/create_playlists", methods=["POST"])
def create_playlists():
    if not refresh_token_if_needed():
        return jsonify({"error": "not logged in"}), 401

    token    = session["access_token"]
    body     = request.json  # list of {id, name, uris, ...}
    created  = []

    for entry in body:
        name  = entry["name"]
        uris  = entry.get("uris", [])
        if not uris: continue

        # Create playlist using POST /me/playlists
        pl = api_post("/me/playlists", token, {
            "name":        name,
            "public":      False,
            "description": f"Curated by Moodify · Intelligent sorting"
        })
        pl_id = pl["id"]

        # Add tracks in batches of 100
        for batch in chunk(uris, 100):
            api_post(f"/playlists/{pl_id}/items", token, {"uris": batch})
            time.sleep(0.1)

        created.append({"name": name, "count": len(uris), "id": pl_id})

    return jsonify({"created": created})

if __name__ == "__main__":
    print("\n🎵 Moodify is running → http://127.0.0.1:5000\n")
    app.run(debug=True, port=5000)
