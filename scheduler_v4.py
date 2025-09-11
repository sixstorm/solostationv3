import sqlite3
import logging
from rich.console import Console
from rich.table import Table
from rich.logging import RichHandler
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
import random
import time
import json

# Logging settings
logging.basicConfig(
    level="INFO",
    format="%(message)s",
    datefmt="[%x]",
    handlers=[RichHandler(rich_tracebacks=True)]
)
log = logging.getLogger("rich")

# Load local env variables
load_dotenv()

# Global Vars
console = Console()

# Classes
class Content:
    def __init__(self, name, type, overview, tvdb_id, tags, runtime, filepath, show_name=None, season_number=None, episode_number=None):
        self.name = name
        self.type = type
        self.overview = overview
        self.tvdb_id = tvdb_id
        self.tags = tags
        self.runtime = runtime
        self.filepath = filepath
        if show_name is not None:
            self.show_name = show_name
        if season_number is not None:
            self.season_number = str(season_number)
        if episode_number is not None:
            self.episode_number = str(episode_number)
        self.start = None
        self.end = None

    def print_as_table(self):
        if self.type == "tv":
            table = Table(title="Content Item")

            table.add_column("Name")
            table.add_column("Type")
            table.add_column("Overview")
            table.add_column("TVDB_ID")
            table.add_column("Tags")
            table.add_column("Runtime")
            table.add_column("Filepath")
            table.add_column("Series")
            table.add_column("Season")
            table.add_column("Episode")

            table.add_row(
                self.name, 
                self.type, 
                self.overview, 
                self.tvdb_id, 
                self.tags, 
                self.runtime, 
                self.filepath,
                self.show_name,
                self.season_number,
                self.episode_number
            )
        elif self.type == "commercial":
            table = Table(title="Content Item")

            table.add_column("Name")
            table.add_column("Type")
            table.add_column("Start")
            table.add_column("End")
            table.add_column("Tags")
            table.add_column("Runtime")
            table.add_column("Filepath")

            table.add_row(self.name, self.type, str(self.start), str(self.end), self.tags, self.runtime, self.filepath)
        else:
            table = Table(title="Content Item")

            table.add_column("Name")
            table.add_column("Type")
            table.add_column("Overview")
            table.add_column("TVDB_ID")
            table.add_column("Tags")
            table.add_column("Runtime")
            table.add_column("Filepath")

            table.add_row(self.name, self.type, self.overview, self.tvdb_id, self.tags, self.runtime, self.filepath)

        console.print(table)

class Slot:
    def __init__(self, start, content=None):
        self.start = start
        self.content = content
        self.size = self.determine_slot_size()
        self.end = self.start + timedelta(minutes=self.size)
        self.comm_time_total = (self.size - (int(float(self.content.runtime)) / 60)) * 60
        self.commercials = []

    def determine_slot_size(self):
        runtime = int(float(self.content.runtime))
        match runtime:
            case _ if (runtime / 60) < 30:
                return 30
            case _ if (runtime / 60) > 30 and (runtime / 60) < 60:
                return 60
            case _ if (runtime / 60) > 60 and (runtime / 60) < 90:
                return 90
            case _ if (runtime / 60) > 90 and (runtime / 60) < 120:
                return 120
            case _ if (runtime / 60) > 120 and (runtime / 60) < 180:
                return 180
            case _ if (runtime / 60) > 180 and (runtime / 60) < 240:
                return 240

    def fill_commercials(self, all_commercials, channel_number, tolerance=5, min_padding=5, max_padding=20):
        marker = self.content.end
        slot_end = get_next_half_hour(marker)
        # logging.info(f"Marker: {marker} - Slot End: {slot_end}")
        # total = timedelta()

        while marker + timedelta(seconds=tolerance) < slot_end:
            # Get all commercials that fit
            candidates = [
                m for m in all_commercials
                if timedelta(seconds=round(int(float(m.runtime)), 2)) <= (slot_end - marker) + timedelta(seconds=tolerance)
            ]

            # Select and add random commercial
            random.shuffle(candidates)
            commercial = candidates[0]
            runtime = round(int(float(commercial.runtime)), 2)
            commercial.start = marker
            commercial.end = marker + timedelta(seconds=runtime)
            self.commercials.append(commercial)
            export_commercial_to_db(commercial, channel_number)
            marker = marker + timedelta(seconds=runtime)
            candidates.pop(0)
        
        time_remaining = slot_end - marker
        logging.debug(f"There is {time_remaining.total_seconds()}s left on the final commercial add")

        if time_remaining > timedelta(seconds=0):
            best = None
            best_diff = float("inf")
            for c in all_commercials:
                runtime = round(int(float(c.runtime)), 2)
                diff = abs(time_remaining.total_seconds() - runtime)
                if diff < best_diff and runtime <= time_remaining.total_seconds() + tolerance:
                    best = c
                    best_diff = diff
            if best:
                runtime = round(int(float(best.runtime)), 2)
                best.start = marker
                best.end = marker + timedelta(seconds=runtime)
                self.commercials.append(best)
                marker = best.end
                export_commercial_to_db(best, channel_number)
                
        return marker
                

class Channel:
    def __init__(self, name, number, description, strategies):
        self.name = name
        self.number = number
        self.description = description
        self.strategies = strategies
        self.schedule = []

class MovieTagStrategyMethod:
    def __init__(self, all_content, tags):
        self.all_content = all_content
        self.tags = tags

    def generate_slots(self, start, duration, channel):
        slots = []
        marker = start
        total = timedelta()

        # Filter Movies by Tag
        movies = [m for m in self.all_content if m.type == "movie"]
        movies = [m for m in movies if [t for t in self.tags if t in m.tags]]
        random.shuffle(movies)

        while total < duration:
            movie = movies[0]
            runtime = round(int(float(movie.runtime)), 2)
            movie.start = marker
            movie.end = marker + timedelta(seconds=runtime)
            slot = Slot(movie.start, movie)
            export_movie_to_db(movie, channel.number)

            # Add commercials
            all_commercials = [m for m in self.all_content if m.type == "commercial"]
            marker = slot.fill_commercials(all_commercials, channel.number)

            # Append slot, pop Content
            slots.append(slot)
            total += timedelta(minutes=slot.size)
            movies.pop(0)

            # logging.info(f"Marker at end of slot fulfillment: {marker}")
            # logging.info(f"{total=} - {duration=}")

        return slots, marker

class TVMarathonStrategyMethod:
    def __init__(self, all_content, series=None, episodes=None):
        self.all_content = all_content

    def generate_slots(self, start, duration, channel):
        slots = []
        marker = start
        total = timedelta()

        self.series = random.choice([s.show_name for s in self.all_content if s.type == 'tv' and s.show_name])
        self.episodes = [e for e in [s for s in self.all_content if s.type == 'tv'] if e.show_name == self.series]

        # Sort episodes by Season and Episode Numbers
        sorted_episodes = sorted(self.episodes, key=lambda x: (int(x.season_number), int(x.episode_number)))

        # Pick a random episode and get the next 20 number of leading episodes
        starting_episode = random.choice(sorted_episodes)
        starting_episode_index = sorted_episodes.index(starting_episode)
        self.episodes = sorted_episodes[starting_episode_index:starting_episode_index+20]

        while total < duration:
            episode = self.episodes[0]
            runtime = round(int(float(episode.runtime)))
            episode.start = marker
            episode.end = marker + timedelta(seconds=runtime)
            slot = Slot(episode.start, episode)
            export_tv_to_db(episode, channel.number)

            # Add commercials
            all_commercials = [m for m in self.all_content if m.type == "commercial"]
            marker = slot.fill_commercials(all_commercials, channel.number)

            # Append slot, pop Content
            slots.append(slot)
            total += timedelta(minutes=slot.size)
            self.episodes.pop(0)

            # logging.info(f"Marker at end of slot fulfillment: {marker}")
            # logging.info(f"{total=} - {duration=}")

        return slots, marker

class PPVStrategyMethod:
    def __init__(self, all_content):
        self.all_content = all_content

    def generate_slots(self, start, duration, channel):
        slots = []
        marker = start
        total = timedelta()

        # Select movie
        movie = random.choice([m for m in self.all_content if m.type == "movie"])
        runtime = timedelta(seconds=round(int(float(movie.runtime)), 2))

        while total < duration:
            movie.start = marker
            movie.end = marker + runtime
            marker = movie.end
            slots.append(Slot(movie.start, movie))
            export_movie_to_db(movie, channel.number)
            total += runtime

        return slots, marker

class MTVStrategyMethod:
    def __init__(self, all_music_videos):
        self.all_music_videos = all_music_videos

    def generate_slots(self, start, duration, channel):
        logging.info("Starting MTV Strategy")
        marker = start
        total = timedelta()
        counter = 0
        video_amount = random.randint(3, 5)

        # Shuffle all music videos
        random.shuffle(self.all_music_videos)

        while total < duration:
            mv = self.all_music_videos[0]
            logging.debug(f"Inserting {mv.filepath} into schedule")
            runtime = timedelta(seconds=round(int(float(mv.runtime)), 2))
            mv.start = marker
            mv.end = marker + runtime

            export_music_video_to_db(mv, channel.number)
            marker = mv.end
            total += runtime
            counter += 1
            self.all_music_videos.pop(0)
            logging.debug(f"{counter=}")
            # time.sleep(0.2)

            # Refill Music Videos
            if len(self.all_music_videos) == 0:
                logging.debug(f"Refilling AMV: {len(self.all_music_videos)}")
                time.sleep(0.2)
                for m in get_all_music_videos_from_db():
                    id, tags, runtime, filepath = m
                    self.all_music_videos.append(Content(filepath, "musicvideo", None, None, tags, runtime, filepath))
                random.shuffle(self.all_music_videos)            

            # Add commercials and idents
            if counter == video_amount:
                # Select random number of commercials
                commercial_amount = random.randint(2,4)
                for c in random.sample(get_all_commercials_from_db(), commercial_amount):
                    # Convert to Content objects and fill in metadata
                    id, tags, runtime, filepath = c
                    logging.debug(f"Inserting {filepath} into schedule")
                    commercial = Content(filepath, "commercial", None, None, tags, runtime, filepath)
                    runtime = timedelta(seconds=round(int(float(commercial.runtime))))
                    commercial.start = marker
                    commercial.end = marker + runtime
                    total += runtime
                    marker = commercial.end

                    # Export commercial directly to schedule DB
                    export_commercial_to_db(commercial, channel.number)

                random_ident = random.choice(get_all_mtv_idents())
                id, tags, runtime, filepath = random_ident
                logging.debug(f"Inserting {filepath} into schedule")
                ident = Content(filepath, "ident", None, None, tags, runtime, filepath)
                runtime = timedelta(seconds=round(int(float(runtime))))
                ident.start = marker
                ident.end = marker + runtime
                marker = ident.end
                total += runtime
                
                export_commercial_to_db(ident, channel.number)

                # Reset counter
                counter = 0
                video_amount = random.randint(3, 5)
                logging.debug(f"{total}/{duration}")
                logging.debug(total < duration)
                time.sleep(0.2)

        logging.debug("Outside of while loop - MTV")
        # time.sleep(1)





class BasicStrategyMethod:
    def __init__(self, all_content):
        self.all_content = all_content
        
    def generate_slots(self, start, duration, channel):
        slots = []
        marker = start
        total = timedelta()

        while total < duration:
            # Update time remaining
            time_remaining = duration - total

            # Get all non-commercial media with a runtime less than time_remaining
            random_media = [m for m in self.all_content if m.type != "commercial" and timedelta(seconds=round(int(float(m.runtime)), 2)) <= time_remaining]
            if not random_media:
                # logging.info(f"Small time to fill: {time_remaining}")
                marker = get_next_half_hour(marker)
                # logging.info(f"Setting marker to {marker}")
                break
                
            # Shuffle and choose random item
            random.shuffle(random_media)
            chosen_content = random_media[0]

            # Prepare content and create the Slot
            runtime = round(int(float(chosen_content.runtime)), 2)
            chosen_content.start = marker
            chosen_content.end = marker + timedelta(seconds=runtime)
            slot = Slot(chosen_content.start, chosen_content)

            # Export to DB
            if chosen_content.type == "tv":
                export_tv_to_db(chosen_content, channel.number)
            if chosen_content.type == "movie":
                export_movie_to_db(chosen_content, channel.number)

            # Add commercials
            all_commercials = [m for m in self.all_content if m.type == "commercial"]
            marker = slot.fill_commercials(all_commercials, channel.number)

            # Append slot, pop Content
            slots.append(slot)
            total += timedelta(minutes=slot.size)
            self.all_content.pop(0)

            # logging.info(f"Marker at end of slot fulfillment: {marker}")
            # logging.info(f"{total=} - {duration=}")

        return slots, marker

# Functions
def initialize_schedule_db():
    logging.info("Initializing Schedule DB")
    with sqlite3.connect(os.getenv("SCHEDULE_DB")) as conn:
        cursor = conn.cursor()

        query = """
            CREATE TABLE IF NOT EXISTS SCHEDULE(
                ID INTEGER PRIMARY KEY AUTOINCREMENT,
                ChannelNumber INTEGER,
                Name TEXT,
                ShowName TEXT,
                Season INTEGER,
                Episode INTEGER,
                Overview TEXT,
                Tags TEXT,
                Runtime TEXT,
                Filepath TEXT,
                Start TEXT,
                End TEXT
            );
        """
        cursor.execute(query)
        conn.commit()
    conn.close()

def export_tv_to_db(content, channel_number):
    with sqlite3.connect(os.getenv("SCHEDULE_DB")) as conn:
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO SCHEDULE (ChannelNumber, Name, ShowName, Season, Episode, Overview, Tags, Runtime, Filepath, Start, End) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                channel_number,
                content.name,
                content.show_name,
                content.season_number,
                content.episode_number,
                content.overview,
                content.tags,
                content.runtime,
                content.filepath,
                datetime.strftime(content.start, "%Y-%m-%d %H:%M:%S"),
                datetime.strftime(content.end, "%Y-%m-%d %H:%M:%S")
            )
        )
        conn.commit()
    conn.close()

def export_movie_to_db(content, channel_number):
    with sqlite3.connect(os.getenv("SCHEDULE_DB")) as conn:
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO SCHEDULE (ChannelNumber, Name, ShowName, Season, Episode, Overview, Tags, Runtime, Filepath, Start, End) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                channel_number,
                content.name,
                None,
                None,
                None,
                content.overview,
                content.tags,
                content.runtime,
                content.filepath,
                datetime.strftime(content.start, "%Y-%m-%d %H:%M:%S"),
                datetime.strftime(content.end, "%Y-%m-%d %H:%M:%S")
            )
        )
        conn.commit()
    conn.close()

def export_commercial_to_db(content, channel_number):
    with sqlite3.connect(os.getenv("SCHEDULE_DB")) as conn:
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO SCHEDULE (ChannelNumber, Name, ShowName, Season, Episode, Overview, Tags, Runtime, Filepath, Start, End) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                channel_number,
                None,
                None,
                None,
                None,
                None,
                "commercial",
                content.runtime,
                content.filepath,
                datetime.strftime(content.start, "%Y-%m-%d %H:%M:%S"),
                datetime.strftime(content.end, "%Y-%m-%d %H:%M:%S")
            )
        )
        conn.commit()
    conn.close()

def export_music_video_to_db(mv, channel_number):
    with sqlite3.connect(os.getenv("SCHEDULE_DB")) as conn:
        cursor = conn.cursor()

        cursor.execute(
            "INSERT INTO SCHEDULE (ChannelNumber, Name, ShowName, Season, Episode, Overview, Tags, Runtime, Filepath, Start, End) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                channel_number,
                None,
                None,
                None,
                None,
                None,
                "musicvideo",
                mv.runtime,
                mv.filepath,
                datetime.strftime(mv.start, "%Y-%m-%d %H:%M:%S"),
                datetime.strftime(mv.end, "%Y-%m-%d %H:%M:%S")
            )
        )
        conn.commit()
    conn.close()

def get_next_half_hour(marker):
    if marker.minute < 30:
        marker = marker.replace(minute=30, second=0, microsecond=0)
    if marker.minute > 30:
        if marker.hour == 23:
            marker = marker.replace(hour=0, minute=0, second=0, microsecond=0)
            marker += timedelta(days=1)
        else:
            marker = marker.replace(hour=(marker.hour + 1), minute=0, second=0, microsecond=0)

    return marker

def print_content_table(channel):
        table = Table(title="Channel Schedule")
        table.add_column("Slot Start")
        table.add_column("Slot End")
        table.add_column("Start")
        table.add_column("End")
        table.add_column("Filepath")

        for block in channel.schedule:
            for slot in block["strategy"]:
                table.add_row(
                    datetime.strftime(slot.start, "%Y-%m-%d %H:%M:%S"),
                    datetime.strftime(slot.end, "%Y-%m-%d %H:%M:%S"),
                    datetime.strftime(slot.content.start, "%Y-%m-%d %H:%M:%S"),
                    datetime.strftime(slot.content.end, "%Y-%m-%d %H:%M:%S"),
                    slot.content.filepath
                )
        
        console.print(table)

def get_all_episodes_from_db():
    with sqlite3.connect(os.getenv("CATALOG_DB")) as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM TV"
        cursor.execute(query)
        return cursor.fetchall()
    cursor.close()

def get_all_movies_from_db():
    with sqlite3.connect(os.getenv("CATALOG_DB")) as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM MOVIES"
        cursor.execute(query)
        return cursor.fetchall()
    cursor.close()

def get_all_commercials_from_db():
    with sqlite3.connect(os.getenv("CATALOG_DB")) as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM COMMERCIALS"
        cursor.execute(query)
        return cursor.fetchall()
    cursor.close()

def get_all_music_videos_from_db():
    with sqlite3.connect(os.getenv("CATALOG_DB")) as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM MUSICVIDEOS"
        cursor.execute(query)
        return cursor.fetchall()
    cursor.close()

def get_all_mtv_idents():
    with sqlite3.connect(os.getenv("CATALOG_DB")) as conn:
        cursor = conn.cursor()
        query = 'SELECT * FROM IDENTS WHERE Tags = "mtvident"'
        cursor.execute(query)
        return cursor.fetchall()
    cursor.close()
    

def clear_schedule_table():
    with sqlite3.connect(os.getenv("SCHEDULE_DB")) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM SCHEDULE")
        conn.commit()
    cursor.close()

def import_channel_data():
    # Import all channels from JSON
    all_channels = []
    with open(os.getenv("CHANNEL_JSON"), "r") as f:
        all_channel_data = json.load(f)
    
    for channel_item in all_channel_data:
        # Create Channel object
        channel = Channel(
            all_channel_data[channel_item]["channel_name"], 
            str(all_channel_data[channel_item]["channel_number"]), 
            all_channel_data[channel_item]["channel_description"],
            all_channel_data[channel_item]["channel_strategies"]        # all_channel_data[channel_item]["templates"]
        )
        all_channels.append(channel)

    return all_channels

def export_schedule(channel):
    with sqlite3.connect(os.getenv("SCHEDULE_DB")) as conn:
        cursor = conn.cursor()

        for block in channel.schedule:
            for slot in block["strategy"]:
                if slot.content:
                    # Insert content into schedule
                    if slot.content.type == "tv":
                        cursor.execute(
                            "INSERT INTO SCHEDULE (ChannelNumber, Name, ShowName, Season, Episode, Overview, Tags, Runtime, Filepath, Start, End) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (
                                channel.number,
                                slot.content.name,
                                slot.content.show_name,
                                slot.content.season_number,
                                slot.content.episode_number,
                                slot.content.overview,
                                slot.content.tags,
                                slot.content.runtime,
                                slot.content.filepath,
                                datetime.strftime(slot.content.start, "%Y-%m-%d %H:%M:%S"),
                                datetime.strftime(slot.content.end, "%Y-%m-%d %H:%M:%S")
                            )
                        )
                        conn.commit()
                    elif slot.content.type == "movie":
                        cursor.execute(
                            "INSERT INTO SCHEDULE (ChannelNumber, Name, ShowName, Season, Episode, Overview, Tags, Runtime, Filepath, Start, End) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (
                                channel.number,
                                slot.content.name,
                                None,
                                None,
                                None,
                                slot.content.overview,
                                slot.content.tags,
                                slot.content.runtime,
                                slot.content.filepath,
                                datetime.strftime(slot.content.start, "%Y-%m-%d %H:%M:%S"),
                                datetime.strftime(slot.content.end, "%Y-%m-%d %H:%M:%S")
                            )
                        )
                        conn.commit()

                    # Insert commercials
                    for commercial in slot.commercials:
                        cursor.execute(
                            "INSERT INTO SCHEDULE (ChannelNumber, Name, ShowName, Season, Episode, Overview, Tags, Runtime, Filepath, Start, End) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                            (
                                channel.number,
                                None,
                                None,
                                None,
                                None,
                                None,
                                "commercial",
                                commercial.runtime,
                                commercial.filepath,
                                datetime.strftime(commercial.start, "%Y-%m-%d %H:%M:%S"),
                                datetime.strftime(commercial.end, "%Y-%m-%d %H:%M:%S")
                            )
                        )
                        conn.commit()

        
    cursor.close()

def create_schedule(channel):
    # Initialize Schedule DB
    initialize_schedule_db()

    logging.info(f"Creating schedule for {channel.name} - {channel.number}")
    # Get all Episodes, Commercials and Movies from Catalog
    all_content = []

    for e in get_all_episodes_from_db():
        id, name, show_name, season_number, episode_number, overview, tvdb_id, tags, runtime, filepath = e
        all_content.append(Content(name, "tv", overview, tvdb_id, tags, runtime, filepath, show_name, season_number, episode_number))

    for m in get_all_movies_from_db():
        id, name, overview, tvdb_id, tags, runtime, filepath = m
        all_content.append(Content(name, "movie", overview, tvdb_id, tags, runtime, filepath))

    for c in get_all_commercials_from_db():
        id, tags, runtime, filepath = c
        all_content.append(Content(filepath, "commercial", None, None, tags, runtime, filepath))

    # Get all unique episode and movie tags
    all_tags = [t.tags for t in all_content]
    unique_tags = list(set([unique_tag for tag_str in all_tags for unique_tag in tag_str.split(",") if tag_str != "commercial"]))

    # Set channel marker to track through the day
    # all_strategies = ["Basic", "MoviesByTag", "TVMarathon"]
    channel_marker = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    channel_end = channel_marker + timedelta(hours=24)

    while channel_marker < channel_end:
        strategy = random.choice(channel.strategies)
        block_duration = timedelta(hours=random.randint(3,5))
        if block_duration > timedelta(hours=(channel_end - channel_marker).total_seconds() / 60 / 60):
            block_duration = timedelta(hours=(channel_end - channel_marker).total_seconds() / 60 / 60)
            # Fill In Strategy Method


        match strategy:
            case "TVMarathon":
                logging.info(f"Strategy: {strategy} - Block Start: {channel_marker} - Block Size: {block_duration}")
                strategy, channel_marker = TVMarathonStrategyMethod(all_content).generate_slots(channel_marker, block_duration, channel)
                block = { "start": channel_marker, "strategy": strategy, "channel_number": channel.number }
            case "MoviesByTag":
                logging.info(f"Strategy: {strategy} - Block Start: {channel_marker} - Block Size: {block_duration}")
                strategy, channel_marker = MovieTagStrategyMethod(all_content, unique_tags).generate_slots(channel_marker, block_duration, channel)
                block = { "start": channel_marker, "strategy": strategy, "channel_number": channel.number }
            case "Basic":
                logging.info(f"Strategy: {strategy} - Block Start: {channel_marker} - Block Size: {block_duration}")
                strategy, channel_marker = BasicStrategyMethod(all_content).generate_slots(channel_marker, block_duration, channel)
                block = { "start": channel_marker, "strategy": strategy, "channel_number": channel.number }
            case "PPV":
                block_duration = timedelta(days=1)
                strategy, channel_marker = PPVStrategyMethod(all_content).generate_slots(channel_marker, block_duration, channel)
                block = { "start": channel_marker, "strategy": strategy, "channel_number": channel.number }
            case "MTV":
                block_duration = timedelta(days=1)
                all_music_videos = []
                for m in get_all_music_videos_from_db():
                    id, tags, runtime, filepath = m
                    all_music_videos.append(Content(filepath, "musicvideo", None, None, tags, runtime, filepath))
                MTVStrategyMethod(all_music_videos).generate_slots(channel_marker, block_duration, channel)
                channel_marker = channel_end              

        if strategy != "MTV":
            channel.schedule.append(block)
    
    export_schedule(channel)

# clear_schedule_table()
# for channel in import_channel_data():
#     create_schedule(channel)