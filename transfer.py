import spotipy
from spotipy.oauth2 import SpotifyOAuth
from ytmusicapi import YTMusic
from rapidfuzz import fuzz
from dotenv import load_dotenv
import os
import time

# --- LOAD ENVIRONMENT VARIABLES ---
load_dotenv()

SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
SPOTIFY_REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT_URI')
SPOTIFY_SCOPE = 'playlist-read-private'

# --- USER INPUT FOR PLAYLIST DETAILS ---

SPOTIFY_PLAYLIST_URL = input("Enter Spotify playlist URL or ID: ").strip()
YTM_PLAYLIST_NAME = input("Enter YouTube Music playlist name (leave blank for default): ").strip()
if not YTM_PLAYLIST_NAME:
    YTM_PLAYLIST_NAME = 'Migrated from Spotify (High Accuracy)'
YTM_PLAYLIST_DESC = input("Enter YouTube Music playlist description (optional): ").strip()
if not YTM_PLAYLIST_DESC:
    YTM_PLAYLIST_DESC = "Imported from Spotify with high accuracy."

# --- AUTHENTICATION ---

sp = spotipy.Spotify(auth_manager=SpotifyOAuth(
    client_id=SPOTIFY_CLIENT_ID,
    client_secret=SPOTIFY_CLIENT_SECRET,
    redirect_uri=SPOTIFY_REDIRECT_URI,
    scope=SPOTIFY_SCOPE
))

ytmusic = YTMusic('browser.json')  # export using browser headers

# --- FETCH SPOTIFY TRACKS ---

def get_spotify_tracks(playlist_url):
    results = sp.playlist_items(playlist_url, additional_types=('track',))
    tracks = []

    while results:
        for item in results['items']:
            track = item.get('track')
            if track is None or track['type'] != 'track':
                continue
            name = track['name']
            artists = [a['name'] for a in track['artists']]
            album = track['album']['name']
            duration_ms = track['duration_ms']
            tracks.append({
                'name': name,
                'artists': artists,
                'album': album,
                'duration_ms': duration_ms
            })
        results = sp.next(results) if results['next'] else None

    return tracks

# --- SEARCH YT MUSIC & MATCH BEST RESULT ---

def find_best_yt_song(track):
    query = f"{track['name']} {' '.join(track['artists'])}"
    search_results = ytmusic.search(query, filter="songs")

    best_match = None
    best_score = 0

    for result in search_results:
        result_title = result['title']
        result_artists = [a['name'] for a in result['artists']]
        result_duration = parse_duration(result['duration']) if 'duration' in result else 0

        title_score = fuzz.token_set_ratio(track['name'], result_title)
        artist_score = fuzz.token_set_ratio(' '.join(track['artists']), ' '.join(result_artists))
        duration_score = 100 - abs(result_duration - track['duration_ms'] // 1000) * 2

        overall_score = (title_score * 0.5) + (artist_score * 0.3) + (duration_score * 0.2)

        if overall_score > best_score:
            best_score = overall_score
            best_match = result

    return best_match if best_score > 75 else None

def find_best_yt_song_relaxed(track):
    # Try searching with only the song name and first artist, and lower threshold
    query = f"{track['name']} {track['artists'][0]}"
    search_results = ytmusic.search(query, filter="songs")

    best_match = None
    best_score = 0

    for result in search_results:
        result_title = result['title']
        result_artists = [a['name'] for a in result['artists']]
        result_duration = parse_duration(result['duration']) if 'duration' in result else 0

        title_score = fuzz.token_set_ratio(track['name'], result_title)
        artist_score = fuzz.token_set_ratio(track['artists'][0], ' '.join(result_artists))
        duration_score = 100 - abs(result_duration - track['duration_ms'] // 1000) * 2

        overall_score = (title_score * 0.6) + (artist_score * 0.3) + (duration_score * 0.1)

        if overall_score > best_score:
            best_score = overall_score
            best_match = result

    return best_match if best_score > 65 else None

def parse_duration(duration_str):
    parts = duration_str.strip().split(':')
    return int(parts[0]) * 60 + int(parts[1]) if len(parts) == 2 else int(parts[0])

# --- MIGRATION PROCESS (ONE BY ONE) ---

def search_and_match_ytm_track(track):
    best_match = find_best_yt_song(track)
    if best_match:
        return best_match['videoId'], "strict"
    else:
        best_match = find_best_yt_song_relaxed(track)
        if best_match:
            return best_match['videoId'], "relaxed"
    return None, None

def process_and_add_one_by_one(ytmusic, playlist_id, spotify_tracks, delay=1):
    total_added = 0
    failed_tracks = []
    for idx, track in enumerate(spotify_tracks):
        video_id, match_type = search_and_match_ytm_track(track)
        if video_id:
            try:
                response = ytmusic.add_playlist_items(playlist_id, [video_id])
                if response.get('status') == 'STATUS_SUCCEEDED':
                    if match_type == "strict":
                        print(f"[{idx+1}/{len(spotify_tracks)}] ✅ Added: {track['name']} -> {video_id}")
                    else:
                        print(f"[{idx+1}/{len(spotify_tracks)}] 🟡 Relaxed match: {track['name']} -> {video_id}")
                    total_added += 1
                else:
                    print(f"[{idx+1}/{len(spotify_tracks)}] ❌ Failed to add: {track['name']} -> {video_id}")
                    failed_tracks.append(track)
            except Exception as e:
                print(f"[{idx+1}/{len(spotify_tracks)}] ❌ Exception for: {track['name']} -> {video_id} | {e}")
                failed_tracks.append(track)
        else:
            print(f"[{idx+1}/{len(spotify_tracks)}] ❌ No match for: {track['name']} - {', '.join(track['artists'])}")
            failed_tracks.append(track)
        time.sleep(delay)
    return total_added, failed_tracks

def transfer_playlist():
    spotify_tracks = get_spotify_tracks(SPOTIFY_PLAYLIST_URL)
    print(f"Found {len(spotify_tracks)} tracks in Spotify playlist.")

    playlist_id = ytmusic.create_playlist(YTM_PLAYLIST_NAME, YTM_PLAYLIST_DESC)
    delay = 1

    total_added, failed_tracks = process_and_add_one_by_one(ytmusic, playlist_id, spotify_tracks, delay)

    print(f"\n✅ Transfer complete. {total_added} tracks attempted to add to YouTube Music.")

    if failed_tracks:
        print(f"\n❌ {len(failed_tracks)} tracks failed to transfer.")
        print("Still failed tracks:")
        for track in failed_tracks:
            print(f"  - {track['name']} - {', '.join(track['artists'])}")

    actual_count = get_ytmusic_playlist_track_count(ytmusic, playlist_id)
    print(f"\n🎵 Playlist now contains {actual_count} tracks on YouTube Music.")

def get_ytmusic_playlist_track_count(ytmusic, playlist_id):
    playlist = ytmusic.get_playlist(playlist_id, limit=10000)
    return len(playlist['tracks'])


# --- MAIN ---

if __name__ == '__main__':
    transfer_playlist()
