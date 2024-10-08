import os
import sys
import random
import pip_system_certs.wrapt_requests  # Use this to fix SSL certificate issues
import spotipy
from tqdm import tqdm
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

# Load environment variables
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


def get_user_playlists(spotifyObject):
    print("Fetching your playlists...")
    playlists = []
    limit = 50
    offset = 0
    with tqdm(desc="Playlists fetched", unit="playlist") as pbar:
        while True:
            results = spotifyObject.current_user_playlists(limit=limit, offset=offset)
            playlists.extend(results["items"])
            pbar.update(len(results["items"]))
            if len(results["items"]) < limit:
                break
            offset += limit
    print(f"Total playlists fetched: {len(playlists)}\n")
    return playlists


def get_playlist_by_name(playlists, names):
    selected_playlists = [p for p in playlists if p["name"] in names]
    if selected_playlists:
        playlist = random.choice(selected_playlists)
        print(f"Randomly selected playlist: '{playlist['name']}'")
        return playlist
    else:
        return None


def get_playlist_tracks(spotifyObject, playlist_id, playlist_name):
    print(f"Fetching tracks from playlist '{playlist_name}'...")
    tracks = []
    limit = 100
    offset = 0
    total = spotifyObject.playlist(playlist_id)["tracks"]["total"]
    with tqdm(total=total, desc=f"Tracks fetched from '{playlist_name}'", unit="track") as pbar:
        while True:
            results = spotifyObject.playlist_items(
                playlist_id, limit=limit, offset=offset, fields="items(track(id,artists(id))),total"
            )
            items = results["items"]
            for item in items:
                track = item["track"]
                if track:
                    track_id = track["id"]
                    artist_id = track["artists"][0]["id"] if track["artists"] else None
                    if track_id and artist_id:
                        tracks.append({"track_id": track_id, "artist_id": artist_id})
                pbar.update(1)
            if len(items) < limit:
                break
            offset += limit
    print(f"Total tracks fetched from '{playlist_name}': {len(tracks)}\n")
    return tracks


def add_tracks_to_playlist(spotifyObject, playlist_id, track_ids):
    print(f"Adding tracks to playlist '{playlist_id}'...")
    limit = 100
    total_batches = (len(track_ids) + limit - 1) // limit
    with tqdm(total=len(track_ids), desc="Tracks added to playlist", unit="track") as pbar:
        for i in range(0, len(track_ids), limit):
            batch = track_ids[i : i + limit]
            spotifyObject.playlist_add_items(playlist_id=playlist_id, items=batch)
            pbar.update(len(batch))
    print("Tracks successfully added to the playlist.\n")


class Mixer(object):
    """
    A Mixer that mixes any number of input streams based upon a set of rules
    Inspired by: https://github.com/declavea/SmarterPlaylists/blob/master/server/mixer.py
    """

    def __init__(self, source_list, dedup=True, min_artist_separation=4, fail_fast=True, max_tracks=1000):
        self.source_list = source_list  # list of lists of dicts with 'track_id' and 'artist_id'
        self.dedup = dedup
        self.min_artist_separation = min_artist_separation
        self.fail_fast = fail_fast
        self.max_tracks = max_tracks

        self.track_history = set()
        self.artist_history = []
        self.cur_channel = 0  # index of current source
        self.prepped = False

        # We need to keep track of the position in each source
        self.source_positions = [0 for _ in source_list]

    def next_track(self):
        self.prep()
        consecutive_fails = 0
        while len(self.source_list) > 0 and len(self.track_history) < self.max_tracks:
            if self.fail_fast and consecutive_fails >= len(self.source_list):
                return None
            candidate_track = self.get_next_candidate()
            if candidate_track is None:
                # No more tracks in this source
                consecutive_fails += 1
                self.next_channel()
            else:
                good = self.good_candidate(candidate_track)
                if good:
                    self.add_to_history(candidate_track)
                    self.next_channel()
                    return candidate_track["track_id"]
                else:
                    consecutive_fails += 1
                    self.next_channel()
        return None

    def add_to_history(self, track):
        self.track_history.add(track["track_id"])
        artist_id = track["artist_id"]
        self.artist_history.append(artist_id)
        # Limit the artist history to enforce min_artist_separation
        if len(self.artist_history) > self.min_artist_separation:
            self.artist_history = self.artist_history[-self.min_artist_separation :]

    def next_channel(self):
        self.cur_channel += 1
        if self.cur_channel >= len(self.source_list):
            self.cur_channel = 0

    def get_next_candidate(self):
        source = self.source_list[self.cur_channel]
        position = self.source_positions[self.cur_channel]
        if position >= len(source):
            # No more tracks in this source
            return None
        track = source[position]
        self.source_positions[self.cur_channel] += 1
        return track

    def good_candidate(self, track):
        if self.dedup and track["track_id"] in self.track_history:
            return False
        artist_id = track["artist_id"]
        if artist_id in self.artist_history:
            # Check artist separation
            return False
        return True

    def prep(self):
        if not self.prepped:
            self.prepped = True


def mix_tracks(source_list, dedup=True, min_artist_separation=4, fail_fast=True, max_tracks=1000):
    print("Mixing tracks using the Mixer algorithm...")
    mixer = Mixer(source_list, dedup, min_artist_separation, fail_fast, max_tracks)
    mixed_tracks = []
    with tqdm(total=max_tracks, desc="Tracks mixed", unit="track") as pbar:
        while True:
            track_id = mixer.next_track()
            if track_id is None:
                break
            mixed_tracks.append(track_id)
            pbar.update(1)
            if len(mixed_tracks) >= max_tracks:
                break
    print(f"Total tracks mixed: {len(mixed_tracks)}\n")
    return mixed_tracks


if __name__ == "__main__":
    # Playlist names
    daily_mix_1_3 = ["Daily Mix 1", "Daily Mix 2", "Daily Mix 3"]
    daily_mix_4_6 = ["Daily Mix 4", "Daily Mix 5", "Daily Mix 6"]
    other_playlists = ["On Repeat", "Repeat Rewind", "Radar des sorties", "Discover Weekly"]

    # Get my playlists
    user_playlists = get_user_playlists(spotifyObject)

    # Randomly select one playlist from Daily Mix 1-3
    daily_mix_1_3_playlist = get_playlist_by_name(user_playlists, daily_mix_1_3)
    if daily_mix_1_3_playlist:
        daily_mix_1_3_tracks = get_playlist_tracks(
            spotifyObject, daily_mix_1_3_playlist["id"], daily_mix_1_3_playlist["name"]
        )
        random.shuffle(daily_mix_1_3_tracks)
    else:
        daily_mix_1_3_tracks = []
        print("No Daily Mix 1-3 playlists found.\n")

    # Randomly select one playlist from Daily Mix 4-6
    daily_mix_4_6_playlist = get_playlist_by_name(user_playlists, daily_mix_4_6)
    if daily_mix_4_6_playlist:
        daily_mix_4_6_tracks = get_playlist_tracks(
            spotifyObject, daily_mix_4_6_playlist["id"], daily_mix_4_6_playlist["name"]
        )
        random.shuffle(daily_mix_4_6_tracks)
    else:
        daily_mix_4_6_tracks = []
        print("No Daily Mix 4-6 playlists found.\n")

    # Get tracks from other playlists
    other_tracks_list = []
    for playlist_name in other_playlists:
        playlist = get_playlist_by_name(user_playlists, [playlist_name])
        if playlist:
            tracks = get_playlist_tracks(spotifyObject, playlist["id"], playlist_name)
            random.shuffle(tracks)
            other_tracks_list.append(tracks)
        else:
            print(f"Playlist '{playlist_name}' not found.\n")

    # Combine all the shuffled tracks into source_list
    source_list = []
    if daily_mix_1_3_tracks:
        source_list.append(daily_mix_1_3_tracks)
    if daily_mix_4_6_tracks:
        source_list.append(daily_mix_4_6_tracks)
    source_list.extend(other_tracks_list)
    if not source_list:
        print("No tracks available to mix. Exiting program...")
        sys.exit()

    # Mix tracks using the Mixer algorithm
    mixed_tracks = mix_tracks(source_list, dedup=True, min_artist_separation=4, fail_fast=True, max_tracks=1000)
    if not mixed_tracks:
        print("No tracks were mixed. Exiting program...")
        sys.exit()
    print(f"Total tracks mixed: {len(mixed_tracks)}\n")

    # Create new playlist
    playlist_name = "[Mixer] Automated Daily Mix"
    playlist_description = "This playlist was created using the Mixer algorithm to combine tracks from your Daily Mix 1-6, On Repeat, Repeat Rewind, Radar des sorties, and Discover Weekly playlists."
    print(f"Creating new playlist '{playlist_name}'...")
    new_playlist = spotifyObject.user_playlist_create(
        user=spotifyObject.current_user()["id"], name=playlist_name, public=False, description=playlist_description
    )
    print(f"Playlist '{playlist_name}' created successfully.\n")

    add_tracks_to_playlist(spotifyObject, new_playlist["id"], mixed_tracks)

    print(f"Mixed tracks successfully uploaded to playlist '{playlist_name}'.")
    print("Process completed.")
