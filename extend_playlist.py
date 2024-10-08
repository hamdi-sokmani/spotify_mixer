import os
import sys
import random
import pip_system_certs.wrapt_requests  # Use this to fix SSL certificate issues
import spotipy
from tqdm import tqdm
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID")
CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET")
REDIRECT_URI = os.getenv("SPOTIPY_REDIRECT_URI")

# Authorization Flow Setup
print("Authenticating with Spotify...")
scope = (
    "playlist-modify-public playlist-modify-private playlist-read-private playlist-read-collaborative user-library-read"
)
token = SpotifyOAuth(scope=scope, client_id=CLIENT_ID, client_secret=CLIENT_SECRET, redirect_uri=REDIRECT_URI)
spotifyObject = spotipy.Spotify(auth_manager=token)
print("Authentication successful.\n")


def get_playlist_by_name(spotifyObject, playlist_name):
    print(f"Searching for playlist '{playlist_name}'...")
    playlists = spotifyObject.current_user_playlists(limit=50)
    for playlist in playlists["items"]:
        if playlist["name"] == playlist_name:
            print(f"Found playlist '{playlist_name}'.\n")
            return playlist
    print(f"Playlist '{playlist_name}' not found.")
    sys.exit(1)


def get_playlist_tracks(spotifyObject, playlist_id, playlist_name):
    print(f"Fetching tracks from playlist '{playlist_name}'...")
    tracks = []
    limit = 100
    offset = 0
    total = spotifyObject.playlist(playlist_id)["tracks"]["total"]
    with tqdm(total=total, desc=f"Tracks fetched from '{playlist_name}'", unit="track") as pbar:
        while True:
            results = spotifyObject.playlist_items(playlist_id, limit=limit, offset=offset, fields="items(track(id))")
            items = results["items"]
            for item in items:
                track = item["track"]
                if track:
                    track_id = track["id"]
                    if track_id:
                        tracks.append(track_id)
                pbar.update(1)
            if len(items) < limit:
                break
            offset += limit
    print(f"Total tracks fetched from '{playlist_name}': {len(tracks)}\n")
    return tracks


def get_audio_features(spotifyObject, track_ids):
    print("Fetching audio features for tracks...")
    audio_features = []
    limit = 100
    with tqdm(total=len(track_ids), desc="Audio features fetched", unit="track") as pbar:
        for i in range(0, len(track_ids), limit):
            batch = track_ids[i : i + limit]
            features = spotifyObject.audio_features(batch)
            audio_features.extend(features)
            pbar.update(len(batch))
    print("Audio features fetched successfully.\n")
    return audio_features


def calculate_average_criteria(audio_features):
    print("Calculating average criteria values...")
    criteria = {
        "instrumentalness": 0.0,
        "energy": 0.0,
        "danceability": 0.0,
        "valence": 0.0,
        "acousticness": 0.0,
    }
    popularity_total = 0
    valid_features_count = 0

    for features in audio_features:
        if features is not None:
            valid_features_count += 1
            criteria["instrumentalness"] += features["instrumentalness"]
            criteria["energy"] += features["energy"]
            criteria["danceability"] += features["danceability"]
            criteria["valence"] += features["valence"]
            criteria["acousticness"] += features["acousticness"]
            # Popularity is not part of audio features, need to fetch it separately
        else:
            print("Warning: Some tracks have no audio features.")

    for key in criteria:
        criteria[key] /= valid_features_count

    # Fetch popularity separately
    print("Fetching track popularity...")
    popularity_total = 0
    limit = 50
    with tqdm(total=len(audio_features), desc="Popularity fetched", unit="track") as pbar:
        for i in range(0, len(audio_features), limit):
            batch_ids = [af["id"] for af in audio_features[i : i + limit] if af]
            tracks = spotifyObject.tracks(batch_ids)
            for track in tracks["tracks"]:
                popularity_total += track["popularity"]
                pbar.update(1)
    average_popularity = popularity_total / valid_features_count
    criteria["popularity"] = average_popularity / 100  # Normalize to 0-1 scale

    print("Average criteria values calculated:\n")
    for key, value in criteria.items():
        print(f"{key.capitalize()}: {value:.2f}")
    print()
    return criteria


def get_seed_tracks_and_artists(track_ids):
    print("Selecting seed tracks and artists...")
    seed_tracks = random.sample(track_ids, min(len(track_ids), 5))
    seed_artists = []
    for track_id in seed_tracks:
        track = spotifyObject.track(track_id)
        artist_id = track["artists"][0]["id"]
        seed_artists.append(artist_id)
    seed_artists = list(set(seed_artists))[:5]  # Max 5 seed artists
    print(f"Selected {len(seed_tracks)} seed tracks and {len(seed_artists)} seed artists.\n")
    return seed_tracks, seed_artists


def generate_recommendations(spotifyObject, criteria, seed_tracks, seed_artists, original_track_ids, limit=1000):
    print("Generating recommendations based on criteria...")
    recommendations = []
    fetched_tracks = set()
    max_limit_per_call = 100  # Maximum allowed by Spotify API per request

    # Prepare parameter ranges, ensuring min <= max
    def prepare_range(value, delta=0.2, min_allowed=0.0, max_allowed=1.0):
        min_value = max(value - delta, min_allowed)
        max_value = min(value + delta, max_allowed)
        if min_value > max_value:
            min_value, max_value = max_value, min_value
        return min_value, max_value

    min_inst, max_inst = prepare_range(criteria["instrumentalness"], 0.2, 0.0, 1.0)
    min_energy, max_energy = prepare_range(criteria["energy"], 0.2, 0.0, 1.0)
    min_dance, max_dance = prepare_range(criteria["danceability"], 0.2, 0.0, 1.0)
    min_valence, max_valence = prepare_range(criteria["valence"], 0.2, 0.0, 1.0)
    min_acoust, max_acoust = prepare_range(criteria["acousticness"], 0.2, 0.0, 1.0)

    min_popularity = max(int(criteria["popularity"] * 100) - 20, 0)
    max_popularity = min(int(criteria["popularity"] * 100) + 20, 100)
    if min_popularity > max_popularity:
        min_popularity, max_popularity = max_popularity, min_popularity

    # Prepare the list of seed combinations
    seed_combinations = []
    seed_tracks = seed_tracks[:5]
    seed_artists = seed_artists[:5]
    random.shuffle(seed_tracks)
    random.shuffle(seed_artists)

    # Limit the number of seed combinations to reduce API calls
    for i in range(min(len(seed_tracks), 2)):
        for j in range(min(len(seed_artists), 2)):
            seed_combinations.append({"seed_tracks": seed_tracks[i : i + 3], "seed_artists": seed_artists[j : j + 2]})

    # If no seed combinations, use tracks or artists alone
    if not seed_combinations:
        if seed_tracks:
            seed_combinations = [{"seed_tracks": seed_tracks[:5]}]
        elif seed_artists:
            seed_combinations = [{"seed_artists": seed_artists[:5]}]
        else:
            print("No seed tracks or artists available for recommendations.")
            return []

    total_requested = 0
    combination_index = 0

    original_track_ids_set = set(original_track_ids)

    with tqdm(total=limit, desc="Recommendations fetched", unit="track") as pbar:
        while len(recommendations) < limit and total_requested < 10000:
            # Cycle through seed combinations
            if combination_index >= len(seed_combinations):
                combination_index = 0
                random.shuffle(seed_combinations)
            seeds = seed_combinations[combination_index]
            combination_index += 1

            params = {
                "limit": min(max_limit_per_call, limit - len(recommendations)),
                "min_instrumentalness": min_inst,
                "max_instrumentalness": max_inst,
                "min_energy": min_energy,
                "max_energy": max_energy,
                "min_danceability": min_dance,
                "max_danceability": max_dance,
                "min_valence": min_valence,
                "max_valence": max_valence,
                "min_acousticness": min_acoust,
                "max_acousticness": max_acoust,
                "min_popularity": min_popularity,
                "max_popularity": max_popularity,
            }
            params.update(seeds)  # Add seed_tracks and/or seed_artists

            try:
                response = spotifyObject.recommendations(**params)
                for track in response["tracks"]:
                    track_id = track["id"]
                    # Exclude duplicates from original playlist and already fetched tracks
                    if track_id not in fetched_tracks and track_id not in original_track_ids_set:
                        fetched_tracks.add(track_id)
                        recommendations.append(track_id)
                        pbar.update(1)
                        if len(recommendations) >= limit:
                            break
                total_requested += params["limit"]
            except spotipy.exceptions.SpotifyException as e:
                print(f"Error fetching recommendations: {e}")
                break

            # Break if no more new tracks are found
            if not response["tracks"]:
                print("No more recommendations available with the current seeds and criteria.")
                break

    print(f"Total unique recommendations fetched: {len(recommendations)}\n")
    return recommendations


def create_playlist_and_add_tracks(spotifyObject, track_ids, original_playlist_name):
    playlist_name = f"Extended {original_playlist_name}"
    playlist_description = f"An extended playlist based on '{original_playlist_name}' with similar songs."
    print(f"Creating new playlist '{playlist_name}'...")
    new_playlist = spotifyObject.user_playlist_create(
        user=spotifyObject.current_user()["id"], name=playlist_name, public=False, description=playlist_description
    )
    print(f"Playlist '{playlist_name}' created successfully.\n")

    # Add tracks to the new playlist
    print(f"Adding tracks to playlist '{playlist_name}'...")
    limit = 100
    with tqdm(total=len(track_ids), desc="Tracks added to playlist", unit="track") as pbar:
        for i in range(0, len(track_ids), limit):
            batch = track_ids[i : i + limit]
            spotifyObject.playlist_add_items(playlist_id=new_playlist["id"], items=batch)
            pbar.update(len(batch))
    print(f"Tracks successfully added to the playlist '{playlist_name}'.\n")
    return new_playlist["external_urls"]["spotify"]


# Main execution
if __name__ == "__main__":
    original_playlist_name = input("Enter the name of the playlist to extend: ")

    # Get original playlist and its tracks
    playlist = get_playlist_by_name(spotifyObject, original_playlist_name)
    track_ids = get_playlist_tracks(spotifyObject, playlist["id"], playlist["name"])
    if not track_ids:
        print("No tracks found in the original playlist. Exiting program...")
        sys.exit(1)

    # Get audio features for tracks and calculate average criteria
    audio_features = get_audio_features(spotifyObject, track_ids)
    criteria = calculate_average_criteria(audio_features)

    seed_tracks, seed_artists = get_seed_tracks_and_artists(track_ids)

    # Generate recommendations based on criteria
    recommendations = generate_recommendations(spotifyObject, criteria, seed_tracks, seed_artists, track_ids, limit=1000)
    if not recommendations:
        print("No recommendations found based on the criteria. Exiting program...")
        sys.exit(1)

    # Create a new playlist
    playlist_url = create_playlist_and_add_tracks(spotifyObject, recommendations, original_playlist_name)

    print(f"Extended playlist created successfully! You can view it here: {playlist_url}")
    print("Process completed.")
