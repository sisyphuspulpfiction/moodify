"""
Moodify - Spotify Mood Playlist Creator
Flask backend
Made By Claude and Gürol :)
"""

from flask import Flask, redirect, request, session, jsonify, render_template
from flask_cors import CORS
import requests
import pandas as pd
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
def assign_mood(track):
    f = track.get("audio_features", {})
    if not f:
        return "Cruising / Everyday"
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
    return jsonify({"name": user.get("display_name", user["id"]),
                    "id":   user["id"],
                    "image": user.get("images", [{}])[0].get("url", "")})

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
                    "album":  t["album"]["name"],
                    "image":  t["album"]["images"][-1]["url"] if t["album"]["images"] else "",
                })
        if data.get("next") is None:
            break
        params["offset"] += 50
        time.sleep(0.1)

    # Fetch audio features in batches of 100 (using individual calls per Feb 2026)
    track_ids = [t["uri"].split(":")[-1] for t in tracks]
    features  = {}

    for batch_ids in chunk(track_ids, 50):
        # GET /audio-features still works for dev mode
        r = requests.get(f"{API_BASE}/audio-features",
                         headers={"Authorization": f"Bearer {token}"},
                         params={"ids": ",".join(batch_ids)})
        if r.status_code == 200:
            for f in r.json().get("audio_features") or []:
                if f:
                    features[f["id"]] = f
        time.sleep(0.1)

    # Assign moods
    mood_map = {}
    for t in tracks:
        tid  = t["uri"].split(":")[-1]
        t["audio_features"] = features.get(tid, {})
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

    session["mood_map"] = {m: [s["uri"] for s in songs]
                           for m, songs in mood_map.items()}
    return jsonify({"total": len(tracks), "moods": summary})

@app.route("/api/create_playlists", methods=["POST"])
def create_playlists():
    if not refresh_token_if_needed():
        return jsonify({"error": "not logged in"}), 401

    token    = session["access_token"]
    mood_map = session.get("mood_map", {})
    body     = request.json  # list of {mood, name, selected}
    created  = []

    for entry in body:
        if not entry.get("selected"):
            continue
        mood  = entry["mood"]
        name  = entry["name"]
        uris  = mood_map.get(mood, [])
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
