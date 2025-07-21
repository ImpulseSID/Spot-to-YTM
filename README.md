# Spot-to-YTM: Spotify Playlist to YouTube Music Migrator

Easily transfer your Spotify playlists to YouTube Music with high accuracy. This tool fetches your Spotify playlist tracks, matches them on YouTube Music, and creates a new playlist for you.

---

## Features

- Authenticates with Spotify and YouTube Music
- Fetches all tracks from a Spotify playlist
- Matches tracks on YouTube Music using fuzzy matching
- **Transfers tracks one by one for reliability**
- Uses a relaxed search if strict matching fails, and reports relaxed matches in the output
- Creates a new playlist on YouTube Music and adds matched tracks
- Reports tracks that could not be matched

---

## Requirements

- Python 3.8+
- Spotify account and developer credentials
- YouTube Music account

---

## Setup

1. **Clone the repository:**

   ```bash
   git clone <repo-url>
   cd spot-to-ytm
   ```

2. **Create and activate a virtual environment:**

   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies:**

   ```bash
   pip install -r requirements.txt
   ```

4. **Set up Spotify Developer App:**

   1. Go to the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard).
   2. Log in with your Spotify account.
   3. Click **"Create an App"**.
   4. Enter an app name and description (anything you like).
   5. Add Redirect URI as `http://127.0.0.1:8888/callback` and also add this to the `SPOTIFY_REDIRECT_URI` in your `.env` file.
   6. Check the box for "Web-API"
   7. Save your changes.
   8. Copy your **Client ID** and **Client Secret** and add this to `SPOTIFY_CLIENT_ID` and `SPOTIFY_CLIENT_SECRET`.

5. **Set up environment variables:**

   - Copy the provided `.env` template and fill in your Spotify credentials:
     ```
     SPOTIFY_CLIENT_ID=your_client_id
     SPOTIFY_CLIENT_SECRET=your_client_secret
     SPOTIFY_REDIRECT_URI=http://127.0.0.1:8888/callback
     ```

6. **Export YouTube Music browser headers:**
   - Follow the steps below to create `browser.json` for Youtube Music authentication.

---

## YouTube Music Authentication (browser.json)

This project uses your browser session headers for YouTube Music authentication.

**How to get your browser headers:**

1. Open [music.youtube.com](https://music.youtube.com) and log in.
2. Open Developer Tools (Ctrl+Shift+I) and go to the "Network" tab.
3. Filter by `/browse` in the search bar.
4. Find a POST request to `/browse` (Status 200).
5. Right-click the request → Copy → Copy request headers.

**Create `browser.json`:**

- Run:
  ```bash
  ytmusicapi browser
  ```
  Paste your copied headers when prompted.  
  This will create a `browser.json` file in your project directory.

Alternatively, in Python:

```python
import ytmusicapi
ytmusicapi.setup(filepath="browser.json", headers_raw="<headers copied above>")
```

Your credentials remain valid as long as your YouTube Music session is active (about 2 years unless you log out).

---

## Usage

Run the transfer script and follow the prompts:

```bash
python transfer.py
```

You will be asked for your Spotify playlist URL/ID, and for the YouTube Music playlist name and description (optional). The script will migrate your playlist and report any tracks that could not be matched.

**How matching works:**

- Each track is searched on YouTube Music using a strict fuzzy match.
- If strict matching fails, a relaxed search is attempted.
- Relaxed matches are indicated in the output as `🟡 Relaxed match`.
- Tracks that cannot be matched are reported at the end.

---

## Notes

- Tracks are transferred **one by one** for reliability; batch transfer is not used.
- Fuzzy matching is used to find the best possible match for each track.
- If a track cannot be found with strict matching, a relaxed search is attempted and reported.
- Some tracks may not be found or matched accurately due to naming or availability differences.
- Your credentials and browser headers are required for authentication.
