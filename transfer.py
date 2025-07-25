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

        # Prefer exact main artist match
        main_artist_match = track['artists'][0].lower() == result_artists[0].lower() if result_artists else False

        # Only consider matches with sufficient artist similarity
        if artist_score < 80 and not main_artist_match:
            continue

        overall_score = (title_score * 0.5) + (artist_score * 0.3) + (duration_score * 0.2)

        # Boost score if main artist matches exactly
        if main_artist_match:
            overall_score += 10

        if overall_score > best_score:
            best_score = overall_score
            best_match = result

    return best_match if best_score > 75 else None

def find_best_yt_song_relaxed(track):
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

        # Prefer exact main artist match
        main_artist_match = track['artists'][0].lower() == result_artists[0].lower() if result_artists else False

        # Only consider matches with sufficient artist similarity
        if artist_score < 80 and not main_artist_match:
            continue

        overall_score = (title_score * 0.6) + (artist_score * 0.3) + (duration_score * 0.1)

        # Boost score if main artist matches exactly
        if main_artist_match:
            overall_score += 10

        if overall_score > best_score:
            best_score = overall_score
            best_match = result

    return best_match if best_score > 55 else None  # lowered from 65

def parse_duration(duration_str):
    parts = duration_str.strip().split(':')
    return int(parts[0]) * 60 + int(parts[1]) if len(parts) == 2 else int(parts[0])

# --- MIGRATION PROCESS (ONE BY ONE) ---

def search_and_match_ytm_track(track):
    best_match = find_best_yt_song(track)
    if best_match:
        return best_match['videoId'], "strict"
    else:
        # Fallback: search videos if song search fails
        query = f"{track['name']} {' '.join(track['artists'])}"
        video_results = ytmusic.search(query, filter="videos")
        if video_results:
            # Try to pick the top result with reasonable duration match
            for result in video_results:
                result_title = result['title']
                result_duration = parse_duration(result['duration']) if 'duration' in result else 0
                # Accept if duration within 30 seconds of Spotify track
                if abs(result_duration - track['duration_ms'] // 1000) <= 30:
                    return result['videoId'], "video"
            # If none match duration, fallback to top video
            return video_results[0]['videoId'], "video"
    return None, None

def process_and_add_one_by_one(ytmusic, playlist_id, spotify_tracks, delay=1):
    total_added = 0
    failed_tracks = []
    video_matches = []
    for idx, track in enumerate(spotify_tracks):
        video_id, match_type = search_and_match_ytm_track(track)
        if video_id:
            try:
                response = ytmusic.add_playlist_items(playlist_id, [video_id])
                if response.get('status') == 'STATUS_SUCCEEDED':
                    if match_type == "strict":
                        print(f"[{idx+1}/{len(spotify_tracks)}] ✅ Added: {track['name']} -> {video_id}")
                    elif match_type == "video":
                        print(f"[{idx+1}/{len(spotify_tracks)}] 🎬 Music video match: {track['name']} -> {video_id}")
                        video_matches.append(track)
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
    return total_added, failed_tracks, video_matches

def transfer_playlist():
    spotify_tracks = get_spotify_tracks(SPOTIFY_PLAYLIST_URL)
    print(f"Found {len(spotify_tracks)} tracks in Spotify playlist.")

    playlist_id = ytmusic.create_playlist(YTM_PLAYLIST_NAME, YTM_PLAYLIST_DESC)
    delay = 1

    total_added, failed_tracks, video_matches = process_and_add_one_by_one(ytmusic, playlist_id, spotify_tracks, delay)

    print(f"\n✅ Transfer complete. {total_added} tracks attempted to add to YouTube Music.")

    if video_matches:
        print(f"\n🎬 {len(video_matches)} tracks matched using music video search (please cross-check):")
        for track in video_matches:
            print(f"  - {track['name']} - {', '.join(track['artists'])}")

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
