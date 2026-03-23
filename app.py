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
GENRE_MOODS = {
    "Hype / Party": ["dance", "edm", "party", "pop", "hip hop", "rap", "r&b", "funk", "disco", "house", "techno", "electro", "trance", "k-pop", "reggaeton"],
    "Pump-Up / Workout": ["rock", "metal", "punk", "hardcore", "trap", "gym", "workout", "phonk", "dubstep", "grime", "breakbeat"],
    "Dark & Intense": ["industrial", "goth", "metal", "dark", "doom", "black metal", "death metal", "techno", "ebm"],
    "Feel-Good / Upbeat": ["indie pop", "happy", "summer", "sunny", "britpop", "j-pop", "nu-disco", "funk", "motown"],
    "Sunny / Laid-Back": ["reggae", "surf", "tropical", "folk pop", "lo-fi", "ska", "afrobeats", "bossa nova"],
    "Melancholic / Moody": ["indie rock", "alternative", "shoegaze", "emo", "grunge", "post-punk", "slowcore", "dream pop"],
    "Acoustic / Soulful": ["soul", "jazz", "blues", "folk", "acoustic", "r&b", "neo soul", "bluegrass", "country"],
    "Calm Acoustic": ["classical", "piano", "acoustic", "singer-songwriter", "chamber", "ambient acoustic", "baroque"],
    "Energetic Instrumental": ["techno", "trance", "house", "drum and bass", "idm", "glitch", "progressive", "jazz fusion"],
    "Ambient / Chill Instrumental": ["ambient", "chillout", "lo-fi", "downtempo", "new age", "minimal", "meditation"],
    "Relaxed / Mellow": ["chill", "smooth", "mellow", "easy listening", "jazz", "lounge", "soft rock", "yacht rock"],
    "Sad / Reflective": ["sad", "melancholy", "ballad", "dark folk", "ambient", "minimal", "modern classical"],
}

def assign_mood(track):
    f = track.get("audio_features", {})
    genres = [g.lower() for g in track.get("genres", [])]

    # Audio feature-based classification
    if f:
        e   = f.get("energy", 0.5)
        v   = f.get("valence", 0.5)
        d   = f.get("danceability", 0.5)
        a   = f.get("acousticness", 0.5)
        ins = f.get("instrumentalness", 0)

        if ins > 0.5:
            return "Ambient / Chill Instrumental" if e < 0.4 else "Energetic Instrumental"
        if e >= 0.75:
            if v >= 0.6 and d >= 0.6: return "Hype / Party"
            if v < 0.4:               return "Dark & Intense"
            return "Pump-Up / Workout"
        if 0.4 <= e < 0.75:
            if v >= 0.65 and d >= 0.6: return "Feel-Good / Upbeat"
            if v >= 0.65 and d < 0.6:  return "Sunny / Laid-Back"
            if v < 0.35:               return "Melancholic / Moody"
            if a >= 0.5:               return "Acoustic / Soulful"
            return "Cruising / Everyday"
        if e < 0.4:
            if a >= 0.5:  return "Calm Acoustic"
            if v < 0.35:  return "Sad / Reflective"
            return "Relaxed / Mellow"

    # Fallback: Genre-based classification
    for mood, keywords in GENRE_MOODS.items():
        if any(kw in g for kw in keywords for g in genres):
            return mood

    return "Cruising / Everyday"

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

    # Paginate through all liked songs
    url    = "/me/tracks"
    params = {"limit": 50, "offset": 0}
    while True:
        data  = api_get(url, token, params)
        items = data.get("items", [])
        if not items:
            break
        for item in items:
            t = item["track"]
            if t:
                tracks.append({
                    "uri":    t["uri"],
                    "name":   t["name"],
                    "artist": ", ".join(a["name"] for a in t["artists"]),
                    "artist_ids": [a["id"] for a in t["artists"]],
                    "album":  t["album"]["name"],
                    "image":  t["album"]["images"][-1]["url"] if t["album"]["images"] else "",
                })
        if data.get("next") is None:
            break
        params["offset"] += 50
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

    # Fetch artist genres as a fallback
    artist_ids = list(set(aid for t in tracks for aid in t.get("artist_ids", [])))
    artist_genres = {}

    # Track if bulk artists endpoint is restricted (403 or 404)
    bulk_artists_restricted = False

    if artist_ids:
        for batch_ids in chunk(artist_ids, 50):
            try:
                if not bulk_artists_restricted:
                    # GET /artists still works for multiple IDs in many cases, but let's be safe
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

                # Fallback to individual calls if plural endpoint is restricted
                for aid in batch_ids:
                    ra = requests.get(f"{API_BASE}/artists/{aid}",
                                     headers={"Authorization": f"Bearer {token}"})
                    if ra.status_code == 200:
                        artist_genres[aid] = ra.json().get("genres", [])
                    elif ra.status_code == 429:
                        print("Rate limited during individual artist fetch, sleeping...")
                        time.sleep(2.0)
                    time.sleep(0.05)
            except Exception as e:
                print(f"Error fetching artist genres: {e}")
            time.sleep(0.1)

    # Assign moods
    mood_map = {}
    for t in tracks:
        tid  = t["uri"].split(":")[-1]
        t["audio_features"] = features.get(tid, {})

        # Attach genres to track for mood assignment
        t["genres"] = []
        for aid in t.get("artist_ids", []):
            t["genres"].extend(artist_genres.get(aid, []))
        t["genres"] = list(set(t["genres"]))

        mood = assign_mood(t)
        t["mood"] = mood
        mood_map.setdefault(mood, []).append(t)

    # Build summary
    summary = []
    for mood, songs in sorted(mood_map.items(), key=lambda x: -len(x[1])):
        summary.append({
            "mood":    mood,
            "emoji":   MOOD_EMOJIS.get(mood, "🎵"),
            "count":   len(songs),
            "songs":   songs[:5],   # preview only
            "all_uris": [s["uri"] for s in songs],
        })

    return jsonify({"total": len(tracks), "moods": summary})

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
