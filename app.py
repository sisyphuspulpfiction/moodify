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

# ─── MOOD LOGIC ──────────────────────────────────────────────────────────────
def assign_mood(track):
    """
    Tiered classification logic for robustness across API restrictions.
    Returns (mood_name, method_used).
    """
    f = track.get("audio_features", {})
    genres = [g.lower() for g in track.get("genres", [])]
    meta_str = f"{track.get('name', '')} {track.get('album', '')} {' '.join(genres)}".lower()

    # Priority 1: Audio features (works for grandfathered Spotify apps)
    if f and any(f.get(k) is not None for k in ("energy", "valence", "danceability")):
        e   = f.get("energy", 0.5)
        v   = f.get("valence", 0.5)
        d   = f.get("danceability", 0.5)
        a   = f.get("acousticness", 0.5)
        ins = f.get("instrumentalness", 0)

        res = "Cruising / Everyday"
        if ins > 0.5:
            res = "Ambient / Chill Instrumental" if e < 0.4 else "Energetic Instrumental"
        elif e >= 0.75:
            if v >= 0.6 and d >= 0.6: res = "Hype / Party"
            elif v < 0.4:             res = "Dark & Intense"
            else:                     res = "Pump-Up / Workout"
        elif 0.4 <= e < 0.75:
            if v >= 0.6 and d >= 0.6: res = "Feel-Good / Upbeat"
            elif v >= 0.6 and d < 0.6:  res = "Sunny / Laid-Back"
            elif v < 0.4:               res = "Melancholic / Moody"
            elif a >= 0.4:               res = "Acoustic / Soulful"
            else:                        res = "Cruising / Everyday"
        elif e < 0.4:
            if a >= 0.5:  res = "Calm Acoustic"
            elif v < 0.35:  res = "Sad / Reflective"
            else:           res = "Relaxed / Mellow"

        if res != "Cruising / Everyday":
            return res, "audio_features"

    # Priority 2: Robust Metadata Keyword search (primary path now)
    # Categorized by specificity and association
    keyword_map = [
        ("Ambient / Chill Instrumental", [
            "ambient", "lofi", "lo-fi", "downtempo", "minimal", "meditation", "new age", "chill instrumental",
            "drone", "background", "study beats", "peaceful instrumental", "atmospheric"
        ]),
        ("Energetic Instrumental", [
            "techno", "house", "trance", "progressive house", "drum and bass", "idm", "glitch", "eurodance",
            "big room", "hardstyle", "jungle", "breakbeat", "instrumental rock"
        ]),
        ("Hype / Party", [
            "dance", "edm", "party", "club", "disco", "remix", "k-pop", "reggaeton", "synthpop", "nu-disco",
            "electropop", "dance-pop", "afro house", "bounce", "festival"
        ]),
        ("Pump-Up / Workout", [
            "metal", "hardcore", "punk", "workout", "gym", "trap", "phonk", "dubstep", "thrash", "deathcore",
            "power metal", "skate punk", "grindcore", "heavy metal", "shred"
        ]),
        ("Dark & Intense", [
            "industrial", "goth", "doom", "dark", "black metal", "death metal", "ebm", "witch house",
            "darkwave", "post-industrial", "funeral doom", "noise"
        ]),
        ("Feel-Good / Upbeat", [
            "happy", "summer", "sunny", "upbeat", "good vibes", "funk", "motown", "britpop", "j-pop",
            "bubblegum", "classic pop", "feel good", "bright"
        ]),
        ("Sunny / Laid-Back", [
            "reggae", "surf", "tropical", "folk pop", "afrobeats", "bossa nova", "ska", "island",
            "summer pop", "yacht rock", "beach", "soft lounge"
        ]),
        ("Melancholic / Moody", [
            "moody", "alternative", "shoegaze", "emo", "grunge", "slowcore", "dream pop", "indie rock",
            "post-punk", "sad indie", "dark pop", "atmospheric rock"
        ]),
        ("Acoustic / Soulful", [
            "soul", "jazz", "blues", "folk", "acoustic", "neo soul", "bluegrass", "unplugged", "singer-songwriter",
            "gospel", "motown soul", "americana", "roots"
        ]),
        ("Calm Acoustic", [
            "classical", "piano", "chamber", "soft", "peaceful", "baroque", "meditative acoustic",
            "solo piano", "contemporary classical", "quiet", "lullaby"
        ]),
        ("Relaxed / Mellow", [
            "smooth", "mellow", "lounge", "soft rock", "easy listening", "chill", "relaxed",
            "cool jazz", "chillout", "trip hop", "downtempo pop", "mellow gold"
        ]),
        ("Sad / Reflective", [
            "sad", "melancholy", "ballad", "dark folk", "modern classical", "heartbreak", "slow",
            "crying", "lonely", "depressing", "gloomy"
        ]),
        ("Cruising / Everyday", [
            "pop", "rock", "hip hop", "rap", "r&b", "indie", "hits", "mainstream", "contemporary",
            "alternative r&b", "top 40", "classic rock", "folk rock", "soft pop"
        ])
    ]

    for mood, keywords in keyword_map:
        if any(kw in meta_str for kw in keywords):
            return mood, "metadata_match"

    return "Cruising / Everyday", "default"

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

@app.route("/api/analyze")
def analyze():
    """Fetch all liked songs + audio features, return mood breakdown."""
    if not refresh_token_if_needed():
        return jsonify({"error": "not logged in"}), 401

    token  = session["access_token"]
    tracks = []

    # Bootstrap artist genres from user's top artists (1 call, 50 artists)
    # This provides a broad genre profile for the user's library
    artist_genres = {}
    try:
        top_artists = api_get("/me/top/artists", token, {"limit": 50})
        for a in top_artists.get("items", []):
            artist_genres[a["id"]] = a.get("genres", [])
    except: pass

    # Paginate through all liked songs
    url    = "/me/tracks"
    params = {"limit": 50, "offset": 0}
    total_to_fetch = None
    while True:
        data  = api_get(url, token, params)
        if total_to_fetch is None:
            total_to_fetch = data.get("total", 0)
        items = data.get("items", [])
        if not items:
            break
        for item in items:
            t = item["track"]
            if t:
                # Get all artist IDs for more comprehensive genre metadata
                artist_ids = [a["id"] for a in t["artists"]]
                tracks.append({
                    "uri":    t["uri"],
                    "name":   t["name"],
                    "artist": ", ".join(a["name"] for a in t["artists"]),
                    "artist_ids": artist_ids,
                    "album":  t["album"]["name"],
                    "image":  t["album"]["images"][-1]["url"] if t["album"]["images"] else "",
                })
        if data.get("next") is None:
            break
        params["offset"] += 50
        print(f"DEBUG: Fetched {len(tracks)}/{total_to_fetch} tracks...")
        time.sleep(0.1)

    # Fetch audio features in batches of 50
    track_ids = [t["uri"].split(":")[-1] for t in tracks]
    features  = {}

    for batch_ids in chunk(track_ids, 50):
        try:
            r = requests.get(f"{API_BASE}/audio-features",
                             headers={"Authorization": f"Bearer {token}"},
                             params={"ids": ",".join(batch_ids)})
            if r.status_code == 200:
                for f in r.json().get("audio_features") or []:
                    if f:
                        features[f["id"]] = f
        except Exception as e:
            print(f"Error fetching audio features: {e}")
        time.sleep(0.1)

    # Count track occurrences per artist to prioritize fetching
    artist_counts = {}
    for t in tracks:
        for aid in t.get("artist_ids", []):
            artist_counts[aid] = artist_counts.get(aid, 0) + 1

    # Fetch artist genres as a fallback
    # Sort artists by track count to prioritize the most impactful ones
    artist_ids = sorted(artist_counts.keys(), key=lambda x: artist_counts[x], reverse=True)

    # Simple JSON cache for artist genres
    cache_file = "artist_cache.json"
    # merge with bootstrapped genres
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "r") as f:
                cached = json.load(f)
                artist_genres.update(cached)
        except: pass

    # Track if bulk artists endpoint is restricted (403 or 404)
    bulk_artists_restricted = False

    # Filter out artists already in cache
    artists_to_fetch = [aid for aid in artist_ids if aid not in artist_genres]

    if artists_to_fetch:
        try:
            for batch_ids in chunk(artists_to_fetch, 50):
                try:
                    if not bulk_artists_restricted:
                        r = requests.get(f"{API_BASE}/artists",
                                         headers={"Authorization": f"Bearer {token}"},
                                         params={"ids": ",".join(batch_ids)})
                        if r.status_code == 200:
                            for a in r.json().get("artists") or []:
                                if a:
                                    artist_genres[a["id"]] = a.get("genres", [])
                            time.sleep(0.1)
                            continue
                        else:
                            print(f"Bulk artists failed ({r.status_code}), falling back to individual calls")
                            if r.status_code in [403, 404]:
                                bulk_artists_restricted = True

                    # Fallback to individual calls
                    for aid in batch_ids:
                        ra = requests.get(f"{API_BASE}/artists/{aid}",
                                         headers={"Authorization": f"Bearer {token}"})
                        if ra.status_code == 200:
                            artist_genres[aid] = ra.json().get("genres", [])
                        elif ra.status_code == 429:
                            wait = int(ra.headers.get("Retry-After", 2))
                            if wait > 5:
                                print(f"Rate limited: Retry-After ({wait}s) is too long. Skipping remaining artists.")
                                raise StopIteration("Rate limit too high")
                            print(f"Rate limited during individual artist fetch, sleeping {wait}s...")
                            time.sleep(wait)
                            # retry once
                            ra = requests.get(f"{API_BASE}/artists/{aid}", headers={"Authorization": f"Bearer {token}"})
                            if ra.status_code == 200:
                                artist_genres[aid] = ra.json().get("genres", [])
                        time.sleep(0.1)
                except StopIteration:
                    raise
                except Exception as e:
                    print(f"Error fetching batch of artists: {e}")
                time.sleep(0.1)
        except StopIteration as si:
            print(f"Stopping artist fetch: {si}")
        except Exception as top_e:
                print(f"Artist fetch loop error: {top_e}")

        # Update cache file
        try:
            with open(cache_file, "w") as f:
                json.dump(artist_genres, f)
        except: pass

    # Debug sample
    sample = tracks[:3]
    for t in sample:
        tid = t["uri"].split(":")[-1]
        print(f"Track: {t['name']} | Features: {features.get(tid)} | Genres: {t.get('genres', [])}")

    # Assign moods
    mood_map = {}
    for t in tracks:
        tid  = t["uri"].split(":")[-1]
        t["audio_features"] = features.get(tid, {})

        # Attach all artist genres to track
        t_genres = []
        for aid in t.get("artist_ids", []):
            t_genres.extend(artist_genres.get(aid, []))
        t["genres"] = list(set(t_genres))

        mood, method = assign_mood(t)
        t["mood"] = mood
        t["method"] = method
        mood_map.setdefault(mood, []).append(t)

    # Build summary
    summary = []
    stats = {"audio_features": 0, "metadata_match": 0, "default": 0}
    for mood, songs in sorted(mood_map.items(), key=lambda x: -len(x[1])):
        for s in songs:
            stats[s["method"]] += 1
        summary.append({
            "mood":    mood,
            "emoji":   MOOD_EMOJIS.get(mood, "🎵"),
            "count":   len(songs),
            "songs":   songs[:5],   # preview only
            "all_uris": [s["uri"] for s in songs],
        })

    return jsonify({"total": len(tracks), "moods": summary, "stats": stats})

@app.route("/api/create_playlists", methods=["POST"])
def create_playlists():
    if not refresh_token_if_needed():
        return jsonify({"error": "not logged in"}), 401

    token    = session["access_token"]
    body     = request.json  # list of {mood, name, selected, uris}
    created  = []

    for entry in body:
        if not entry.get("selected"):
            continue
        mood  = entry["mood"]
        name  = entry["name"]
        uris  = entry.get("uris", [])
        if not uris:
            continue

        # Create playlist using POST /me/playlists (Feb 2026 endpoint)
        pl = api_post("/me/playlists", token, {
            "name":        name,
            "public":      False,
            "description": f"Created by Moodify · {mood}"
        })
        pl_id = pl["id"]

        # Add tracks in batches of 100
        for batch in chunk(uris, 100):
            api_post(f"/playlists/{pl_id}/items", token, {"uris": batch})
            time.sleep(0.2)

        created.append({"name": name, "count": len(uris), "id": pl_id})

    return jsonify({"created": created})

if __name__ == "__main__":
    print("\n🎵 Moodify is running → http://127.0.0.1:5000\n")
    app.run(debug=True, port=5000)
