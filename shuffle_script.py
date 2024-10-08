import sys
import os
import pip_system_certs.wrapt_requests  # Use this to fix SSL certificate issues
import spotipy
from tqdm import tqdm
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv
import random

# Load environment variables from .env file
load_dotenv()

CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI")

# Authorization Flow Setup
print("Authenticating with Spotify...")
scope = "playlist-modify-public playlist-modify-private playlist-read-private playlist-read-collaborative"
token = SpotifyOAuth(scope=scope, client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_uri=REDIRECT_URI)
spotifyObject = spotipy.Spotify(auth_manager=token)
print("Authentication successful.\n")

if __name__ == "__main__":
    playlist_name = "[Mixer] Automated Radio Mix"
    user_id = spotifyObject.current_user()["id"]

    # Fetch the existing playlist
    existing_playlist = None
    playlists = spotifyObject.current_user_playlists(limit=50)
    for playlist in playlists["items"]:
        if playlist["name"] == playlist_name:
            existing_playlist = playlist
            break

    if existing_playlist:
        print(f"Fetching tracks from playlist '{playlist_name}' for shuffling...")
        playlist_id = existing_playlist["id"]
        track_ids = []
        offset = 0
        limit = 100
        while True:
            response = spotifyObject.playlist_items(
                playlist_id, offset=offset, limit=limit, fields="items(track(id)),total"
            )
            items = response["items"]
            for item in items:
                track = item["track"]
                if track:
                    track_ids.append(track["id"])
            if len(items) < limit:
                break
            offset += limit

        # Shuffle the tracks
        print("Shuffling tracks...")
        random.shuffle(track_ids)

        # Replace the playlist with the shuffled tracks
        print("Updating playlist with shuffled tracks...")
        # First clear the playlist
        spotifyObject.playlist_replace_items(playlist_id, [])
        # Add shuffled tracks
        limit = 100
        with tqdm(total=len(track_ids), desc="Adding shuffled tracks", unit="track") as pbar:
            for i in range(0, len(track_ids), limit):
                batch = track_ids[i : i + limit]
                spotifyObject.playlist_add_items(playlist_id, batch)
                pbar.update(len(batch))
        print(f"Playlist '{playlist_name}' updated with shuffled tracks.")
    else:
        print(f"Playlist '{playlist_name}' not found. Exiting program...")
        sys.exit(1)

    print("All scripts executed successfully.")
