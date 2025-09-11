import sqlite3
import tvdb_v4_official
import re
import os
from dotenv import load_dotenv
import glob
import json
import ffmpeg
from rich import print
import time

# Load local env variables
load_dotenv()

# Global Vars
tv_root = os.getenv("TV_ROOT")
movie_root = os.getenv("MOVIE_ROOT")
comm_root = os.getenv("COMM_ROOT")
music_root = os.getenv("MUSIC_ROOT")
mtv_ident_root = os.getenv("MTV_IDENT_ROOT")

# SQLite Vars
conn = sqlite3.connect(os.getenv("CATALOG_DB"))
cursor = conn.cursor()

def connect_tvdb():
    api_key = os.getenv("TVDB_API_KEY")
    return tvdb_v4_official.TVDB(api_key)

def initialize_tables():
    # TV
    query = """
        CREATE TABLE IF NOT EXISTS TV(
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            Name TEXT,
            ShowName TEXT,
            Season INTEGER,
            Episode INTEGER,
            Overview TEXT,
            TVDB_ID TEXT,
            Tags TEXT,
            Runtime TEXT,
            Filepath TEXT
        );
    """

    cursor.execute(query)

    # Commercials
    query = """
        CREATE TABLE IF NOT EXISTS COMMERCIALS(
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            Tags TEXT,
            Runtime TEXT,
            Filepath TEXT
        );
    """

    cursor.execute(query)
    
    # Music Videos
    query = """
        CREATE TABLE IF NOT EXISTS MUSICVIDEOS(
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            Tags TEXT,
            Runtime TEXT,
            Filepath TEXT
        );
    """

    cursor.execute(query)
    
    # Idents
    query = """
        CREATE TABLE IF NOT EXISTS IDENTS(
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            Tags TEXT,
            Runtime TEXT,
            Filepath TEXT
        );
    """

    cursor.execute(query)
    
    # Movies
    query = """
        CREATE TABLE IF NOT EXISTS MOVIES(
            ID INTEGER PRIMARY KEY AUTOINCREMENT,
            Name TEXT,
            Overview TEXT,
            TVDB_ID TEXT,
            Tags TEXT,
            Runtime TEXT,
            Filepath TEXT
        );
    """
    cursor.execute(query)
    
    # # Schedule
    # query = """
    #     CREATE TABLE IF NOT EXISTS SCHEDULE(
    #         ID INTEGER PRIMARY KEY AUTOINCREMENT,
    #         ChannelNumber INTEGER,
    #         Name TEXT,
    #         ShowName TEXT,
    #         Season INTEGER,
    #         Episode INTEGER,
    #         Overview TEXT,
    #         Tags TEXT,
    #         Runtime TEXT,
    #         Filepath TEXT,
    #         Start TEXT,
    #         End TEXT
    #     );
    # """
    # cursor.execute(query)

    conn.commit()

def check_in_table(table, file):
    with sqlite3.connect(os.getenv("CATALOG_DB")) as conn:
        cursor = conn.cursor()
        query = f'SELECT * FROM {table} WHERE Filepath="{file}"'
        cursor.execute(query)
        if cursor.fetchone():
            return True
        else:
            return False
    cursor.close()

def get_runtime(file):
    """
    Return duration of file in seconds

    Args:
        file (str): Filename of video

    Returns:
        float: Video duration in seconds
    """

    probe = ffmpeg.probe(file)
    duration = str(round(float(probe["format"]["duration"]), 2))
    return duration

def update_movie_tags():
    with sqlite3.connect(os.getenv("CATALOG_DB")) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM MOVIES")
        all_movie_data = cursor.fetchall()

        for movie_data in all_movie_data:
            # Get movie name
            movie_name = movie_data[1]

            # Get movie JSON file
            movie_extended_json = f"metadata/movies/{movie_name}-extended.json"

            if os.path.exists(movie_extended_json):
                print(f"Found {movie_extended_json}")

                # Read extended JSON file for movie
                with open(movie_extended_json, "r") as file:
                    movie_extended_json_data = json.load(file)

                    # Generate tags
                    json_tags = [g["name"].lower() for g in movie_extended_json_data["genres"]]
                    print(f"Found {len(json_tags)} for {movie_name}")
                    print(json_tags)
                    tags = str(",".join(json_tags))
                    new_tags = f"movie,{tags}"

                    # Compare with existing tags
                    if new_tags != movie_data[3]:
                        # Write tags back to Catalog
                        cursor.execute("UPDATE Movies SET Tags=(?) WHERE ID=(?)", (new_tags, movie_data[0]))
                        conn.commit()
                        # time.sleep(1)
            else:
                print(f"Could not find file {movie_extended_json}")
    conn.close()

def update_tv_tvdb_id():
    with sqlite3.connect(os.getenv("CATALOG_DB")) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM TV")
        all_tv_items = cursor.fetchall()

        for episode in all_tv_items:
            episode_name = episode[1]
            print(episode[1])

            with open(f"metadata/tv/{episode[2]}_episodes.json", "r") as file:
                found_episode_metadata = [e["id"] for e in json.load(file) if e["name"] == episode_name]
                if found_episode_metadata:
                    print(f"Found {episode_name} and ID {found_episode_metadata[0]}")
                    # time.sleep(1)


def process_tv():
    print("Processing all TV episodes")
    
    # Walk through each TV folder, downloading all metadata
    for show_root_folder in next(os.walk(tv_root))[1]:

        # Parsing and fetching metadata
        show_name = re.search(".+?(?=\s\()", show_root_folder)[0]
        show_year = re.search("\(([0-9]{4})\)", show_root_folder)[1]
        series_full_json_file = f"metadata/tv/{show_name}.json"
        episode_json_file = f"metadata/tv/{show_name}_episodes.json"
        
        # Download Series Metadata if it doesn't exist
        if not os.path.exists(series_full_json_file):
            print(f"Searching for {show_name} - {show_year}")
            try:
                results = tvdb.search(show_name)  # Return list of dicts
                print(f"Found {len(results)} results\n")

                # Filters results to show year and series only
                series_full_data = [s for s in results if "year" in s and s["type"] == "series" and s["year"] == show_year][0]

                # Export series metadata from TVDB into JSON files
                with open(series_full_json_file, "w") as file:
                    json.dump(series_full_data, file, indent=4)
            except Exception as e:
                print(f"Failed to export JSON: {e}")

        # Read local series JSON file
        with open(series_full_json_file, "r") as file:
            series_local_data = json.load(file)

        # Download all episode metadata from TVDB if it doesn't exist
        if not os.path.exists(episode_json_file):
            print("Episode metadata file not found; grabbing from TVDB")
            try:
                page = 0
                all_episodes = []

                while True:
                    episode_data = tvdb.get_series_episodes(series_local_data["tvdb_id"], page=page)
                    print(f"Found {len(episode_data)} on episode_data")
                    episodes = episode_data.get("episodes", [])
                    print(f"Found {len(episodes)} on page")
                    if not episodes:
                        break

                    all_episodes.extend(episodes)
                    page += 1
                
                print(f"Found {len(all_episodes)} episodes")

                with open(episode_json_file, "w") as file:
                    json.dump(all_episodes, file, indent=4)
            except Exception as e:
                print(f"Failed to export episode metadata: {e}")

        # Read local episode JSON file
        with open(episode_json_file, "r") as file:
            episode_local_data = json.load(file)

        # Go through each episode and store data in the Catalog
        all_episode_files = glob.glob(f"{tv_root}/{show_root_folder}/*/*.mp4", recursive=True) + glob.glob(f"{tv_root}/{show_root_folder}/*/*.mkv", recursive=True)
        print(f"Found {len(all_episode_files)} for {tv_root}/{show_root_folder}")
        for episode in all_episode_files:
            if not check_in_table("TV", episode):
                print(f"Episode {episode} is not in the Catalog")

                # Parse season and episode number
                season_number = re.search("S(\d{2})", episode).group(1)
                if season_number.startswith("0"):
                    season_number.lstrip("0")
                episode_number = re.search("E(\d{2})", episode).group(1)
                if episode_number.startswith("0"):
                    episode_number.lstrip("0")

                # Find episode data in episode_metadata
                try:
                    episode_metadata = [
                        e
                        for e in episode_local_data
                        if e["seasonNumber"] == int(season_number)
                        and e["number"] == int(episode_number)
                    ][0]

                    try:
                        tags = ["tv"]
                        # for tag in series_local_data["genres"]:
                        #     tags.append(tag["name"].lower())
                        tags = str(",".join(tags))

                        # Insert episode into Catalog
                        # print(f"Inserting:\n{episode_metadata['name']}\n{show_name}\n{season_number}\n{episode_number}\n{episode_metadata['overview']}\n{tags}\n{episode}\n")
                        print(f"Inserting: {episode_metadata['name']}")
                        cursor.execute(
                            "INSERT INTO TV (Name, ShowName, Season, Episode, Overview, TVDB_ID, Tags, Runtime, Filepath) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (
                                episode_metadata["name"],
                                show_name,
                                season_number,
                                episode_number,
                                episode_metadata["overview"],
                                episode_metadata["id"],
                                tags,
                                get_runtime(episode),
                                episode
                            ),
                        )
                        conn.commit()
                    except Exception as e:
                        print(f"Cannot process metadata: {e}")
                except Exception as e:
                    print(f"Episode metadata error: {e}")
                
def process_commercials():
    print("Processing all commercials")
    
    # Get runtime of each commercial and insert into Catalog
    for comm in glob.glob(f"{comm_root}/*/*.mp4"):
        if not check_in_table("COMMERCIALS", comm):
            tags = str(",".join(["commercial"]))
            print(f"Inserting: {comm}")
            cursor.execute(
                "INSERT INTO COMMERCIALS (Tags, Runtime, Filepath) VALUES (?, ?, ?)",
                (
                    tags,
                    get_runtime(comm),
                    comm
                )
            )
            conn.commit()

def process_music_videos():
    print("Processing all music videos")
    
    # Get runtime of each music video and insert into Catalog
    for mv in glob.glob(f"{music_root}/*.mp4"):
        if not check_in_table("MUSICVIDEOS", mv):
            tags = str(",".join(["musicvideo"]))
            print(f"Inserting: {mv}")
            cursor.execute(
                "INSERT INTO MUSICVIDEOS (Tags, Runtime, Filepath) VALUES (?, ?, ?)",
                (
                    tags,
                    get_runtime(mv),
                    mv
                )
            )
            conn.commit()

def process_mtv_idents():
    print("Processing MTV Idents")

    # Get runtime of each MTV ident and insert into Catalog
    for ident in glob.glob(f"{mtv_ident_root}/*.mp4"):
        if not check_in_table("IDENTS", ident):
            tags = str(",".join(["mtvident"]))
            print(f"Inserting: {ident}")
            cursor.execute(
                "INSERT INTO IDENTS (Tags, Runtime, Filepath) VALUES (?, ?, ?)",
                (
                    tags,
                    get_runtime(ident),
                    ident
                )
            )
            conn.commit()


def process_movies():
    print("Processing all movies")
    # Walk through each Movie folder, downloading all metadata
    for movie_root_folder in next(os.walk(movie_root))[1]:

        # Parse into metadata
        movie_name = re.search(".+?(?=\s\()", movie_root_folder)[0]
        movie_year = re.search("\(([0-9]{4})\)", movie_root_folder)[1]
        movie_json_file = f"metadata/movies/{movie_name}.json"
        movie_ext_json_file = f"metadata/movies/{movie_name}-extended.json"
        
        if not os.path.exists(movie_json_file) or not os.path.exists(movie_ext_json_file):
            print(f"Searching for {movie_name} - {movie_year}")
            try:
                # Filter results
                movie_full_data = [m for m in tvdb.search(movie_name) if "year" in m and m["type"] == "movie" and m["year"] == movie_year][0]
                movie_ext_full_data = tvdb.get_movie_extended(movie_full_data["tvdb_id"])

                # Export movie metadata from TVDB into JSON files
                with open(movie_json_file, "w") as file:
                    json.dump(movie_full_data, file, indent=4)
                with open(movie_ext_json_file, "w") as file:
                    json.dump(movie_ext_full_data, file, indent=4)
            except Exception as e:
                print(f"Failed to export JSON: {e}")

        # Get movie filepath
        try:
            movie = (glob.glob(f"{movie_root}/{movie_root_folder}/*.mp4") + glob.glob(f"{movie_root}/{movie_root_folder}/*.mkv"))[0]
            print(f"Processing {movie}")
        except IndexError as e:
            print(e)
            continue
        
        if not check_in_table("MOVIES", movie):
            with sqlite3.connect(os.getenv("CATALOG_DB")) as conn:
                cursor = conn.cursor()

                # Get movie metadata and extended metadata from local file
                with open(movie_json_file, "r") as file:
                    movie_metadata = json.load(file)
                with open(movie_ext_json_file, "r") as file:
                    movie_ext_metadata = json.load(file)

                # Define tags
                tags = [g["name"].lower() for g in movie_ext_metadata["genres"]]
                tags = str(",".join(tags))
                tags = f"movie,{tags}"

                # Insert movie into Catalog
                try:
                    cursor.execute(
                        "INSERT INTO MOVIES (Name, Overview, TVDB_ID, Tags, Runtime, Filepath) VALUES (?, ?, ?, ?, ?, ?)",
                        (
                            movie_metadata["name"],
                            movie_metadata["overview"],
                            movie_metadata["tvdb_id"],
                            tags,
                            get_runtime(movie),
                            movie
                        ),
                    )
                    conn.commit()
                except Exception as e:
                    print(f"Could not insert {movie} into Catalog: {e}")
            conn.close()
        


# Main
# Connect to TVDB API
tvdb = connect_tvdb()

# Initialize all SQLite Tables
initialize_tables()

# Process all TV shows
process_tv()

# Process all Commercials
process_commercials()

# Process all music videos
process_music_videos()

# Process all MTV idents
process_mtv_idents()

# Process all Movies
process_movies()

# update_movie_tags()