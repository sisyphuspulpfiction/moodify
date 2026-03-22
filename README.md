# 🎵 Moodify

**Moodify** analyzes your Spotify liked songs and automatically creates mood-based playlists using Spotify's audio features (energy, valence, danceability, acousticness).

![Python](https://img.shields.io/badge/python-3.8+-blue) ![Flask](https://img.shields.io/badge/flask-3.0-green) ![Spotify](https://img.shields.io/badge/spotify-API-1DB954)

---

## Moods

| Mood | Description |
|---|---|
| 🎉 Hype / Party | High energy, positive, danceable |
| 💪 Pump-Up / Workout | High energy, driving tempo |
| 🌑 Dark & Intense | High energy, low valence |
| 😄 Feel-Good / Upbeat | Mid energy, happy, danceable |
| ☀️ Sunny / Laid-Back | Mid energy, positive, relaxed |
| 😔 Melancholic / Moody | Mid energy, low valence |
| 🎸 Acoustic / Soulful | Mid energy, acoustic |
| 🚗 Cruising / Everyday | Balanced everything |
| 🎵 Calm Acoustic | Low energy, acoustic |
| ⚡ Energetic Instrumental | High instrumentalness, energetic |
| 🌙 Ambient / Chill Instrumental | High instrumentalness, calm |
| 😌 Relaxed / Mellow | Low energy, positive |
| 💧 Sad / Reflective | Low energy, low valence |

---

## Setup

### 1. Clone the repo
```bash
git clone https://github.com/yourusername/moodify
cd moodify
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Create a Spotify App
1. Go to [developer.spotify.com/dashboard](https://developer.spotify.com/dashboard)
2. Click **Create App**
3. Set the Redirect URI to: `http://127.0.0.1:5000/callback`
4. Copy your **Client ID** and **Client Secret**

### 4. Set environment variables

**Windows:**
```cmd
set SPOTIFY_CLIENT_ID=your_client_id_here
set SPOTIFY_CLIENT_SECRET=your_client_secret_here
```

**Mac / Linux:**
```bash
export SPOTIFY_CLIENT_ID=your_client_id_here
export SPOTIFY_CLIENT_SECRET=your_client_secret_here
```

### 5. Run
```bash
python app.py
```

Open your browser at **http://127.0.0.1:5000**

---

## How it works

1. You log in with Spotify — Moodify fetches all your liked songs
2. For each song, Spotify's audio features API returns values like `energy`, `valence`, `danceability`, `acousticness`, and `instrumentalness`
3. A rule-based classifier assigns each song to a mood bucket
4. You see the breakdown, preview songs per mood, rename playlists, deselect moods you don't want
5. Click **Create Playlists** — done

---

## Notes

- Works with both Spotify Free and Premium accounts
- Due to Spotify's Dev Mode restrictions (Feb 2026), the app supports up to **5 users**
- All playlists are created as **private** by default
- No data is stored — everything runs locally

---

## License

MIT
