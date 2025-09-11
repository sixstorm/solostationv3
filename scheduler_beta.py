import sqlite3
import logging
from rich import print
from rich import print_json
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
all_channels = []

# Classes
class Episode():
    def __init__(self, name, show_name, season_number, episode_number, overview, tags, runtime, filepath):
        self.name = name
        self.show_name = show_name
        self.season_number = season_number
        self.episode_number = episode_number
        self.overview = overview
        self.tags = tags
        self.runtime = runtime
        self.filepath = filepath

    def __str__(self):
        return f"Show: {self.show_name}\nName: {self.name}\nFilepath: {self.filepath}"

class Movie():
    def __init__(self, name, overview, tvdb_id, tags, runtime, filepath):
        self.name = name
        self.overview = overview
        self.tvdb_id = tvdb_id
        self.tags = tags
        self.runtime = runtime
        self.filepath = filepath

class Commercial():
    def __init__(self, tags, runtime, filepath):
        self.tags = tags
        self.runtime = runtime
        self.filepath = filepath
        self.start = ""
        self.end = ""

    def __str__(self):
        return f"Commercial: {self.filepath}"

class Program():
    def __init__(self, name, show_name, season_number, episode_number, overview, tags, runtime, filepath, start, end):
        self.name = name
        self.show_name = show_name
        self.season_number = season_number
        self.episode_number = episode_number
        self.overview = overview
        self.tags = tags
        self.runtime = runtime
        self.filepath = filepath
        self.start = start
        self.end = end

    def to_dict(self):
        return {
            "name": self.name, 
            "show_name": self.show_name, 
            "season_number": self.season_number,
            "episode_number": self.episode_number,
            "overview": self.overview,
            "tags": self.tags,
            "runtime": self.runtime,
            "filepath": self.filepath
        }

    def __str__(self):
        if self.season_number:
            return f"{self.show_name}-{self.name} - S{self.season_number}E{self.episode_number}"
        else:
            return f"{self.name}"

class Slot():
    def __init__(self, start):
        self.start =start
        self.size = 0
        self.end = None
        self.layout = []

    def show_slot(self):
        table = Table(title="Current slot")
        table.add_column("Show")
        table.add_column("Filepath")
        table.add_column("Start")
        table.add_column("End")

        for item in self.layout:
            # If the currently playing item, highlight in bold red for visibility
            now = datetime.now()
            if now >= item.start and now <= item.end:
                if isinstance(item, Program):
                    table.add_row(
                        item.show_name,
                        item.filepath,
                        str(item.start),
                        str(item.end), 
                        style="bold red"
                    )
                else:
                    table.add_row(
                        None,
                        item.filepath,
                        str(item.start),
                        str(item.end),
                        style="bold green"
                    )
            else:
                if isinstance(item, Program):
                    table.add_row(
                        item.show_name,
                        item.filepath,
                        str(item.start),
                        str(item.end)
                    )
                else:
                    table.add_row(
                        None,
                        item.filepath,
                        str(item.start),
                        str(item.end)
                    )

        console.print(table)


    def determine_slot_size(self, program):
        runtime = int(float(program.runtime))
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

class Block():
    def __init__(self, name, start, end, tags):
        self.name = name
        self.start = start
        self.end = end
        self.tags = tags
        self.slots = []

    def add_slot(self, slot):
        self.slots.append(slot)

class Channel():
    def __init__(self, name, number, description, start, end, rules):
        self.name = name
        self.number = number
        self.description = description
        self.start = start
        self.end = end
        self.rules = rules
        self.schedule = []

    def show_channel(self):
        table = Table(title=f"Schedule for {self.channel_name}")

        table.add_column("Show Name")
        table.add_column("Episode")
        table.add_column("Slot Start")
        table.add_column("Slot End")
        table.add_column("Show Start")
        table.add_column("Show End")
        table.add_column("Commercials")

        for block in self.schedule:
            for slot in block.slots:
                if not isinstance(slot.layout[0], Movie):
                    table.add_row(
                        slot.layout[0].show_name, 
                        slot.layout[0].name,
                        datetime.strftime(slot.start, "%Y-%m-%d %H:%M:%S"),
                        datetime.strftime(slot.end, "%Y-%m-%d %H:%M:%S"),
                        datetime.strftime(slot.layout[0].start, "%Y-%m-%d %H:%M:%S"),
                        datetime.strftime(slot.layout[0].end, "%Y-%m-%d %H:%M:%S"),
                        str(len(slot.layout[1:]))
                    )
                else:
                    table.add_row(
                        None, 
                        slot.layout[0].name,
                        datetime.strftime(slot.start, "%Y-%m-%d %H:%M:%S"),
                        datetime.strftime(slot.end, "%Y-%m-%d %H:%M:%S"),
                        datetime.strftime(slot.layout[0].start, "%Y-%m-%d %H:%M:%S"),
                        datetime.strftime(slot.layout[0].end, "%Y-%m-%d %H:%M:%S"),
                        str(len(slot.layout[1:]))
                    )

        console.print(table)

    def show_channel_by_block(self):
        for block in self.schedule:
            table = Table(title=f"{block.name}")

            table.add_column("Show Name")
            table.add_column("Episode")
            table.add_column("Slot Start")
            table.add_column("Slot End")
            table.add_column("Show Start")
            table.add_column("Show End")
            table.add_column("Commercials")

            for slot in block.slots:
                table.add_row(
                    slot.layout[0].show_name, 
                    slot.layout[0].name,
                    datetime.strftime(slot.start, "%Y-%m-%d %H:%M:%S"),
                    datetime.strftime(slot.end, "%Y-%m-%d %H:%M:%S"),
                    datetime.strftime(slot.layout[0].start, "%Y-%m-%d %H:%M:%S"),
                    datetime.strftime(slot.layout[0].end, "%Y-%m-%d %H:%M:%S"),
                    str(len(slot.layout[1:]))
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

def show_schedule_table(slots):
    table = Table(title="Schedule")

    table.add_column("Show Name")
    table.add_column("Episode")
    table.add_column("Slot Start")
    table.add_column("Slot End")
    table.add_column("Show Start")
    table.add_column("Show End")
    table.add_column("Commercials")

    for Slot in slots:
        table.add_row(
            Slot.program.show_name, 
            Slot.program.name,
            datetime.strftime(Slot.start, "%Y-%m-%d %H:%M:%S"),
            datetime.strftime(Slot.end, "%Y-%m-%d %H:%M:%S"),
            datetime.strftime(Slot.program.start, "%Y-%m-%d %H:%M:%S"),
            datetime.strftime(Slot.program.end, "%Y-%m-%d %H:%M:%S"),
            str(Slot.commtime)
        )

    console.print(table)

  

def import_channel_data():
    # Import all channels from JSON
    with open(os.getenv("CHANNEL_JSON"), "r") as f:
        all_channel_data = json.load(f)
    
    for channel_item in all_channel_data:
        # Create Channel object
        channel = Channel(
            all_channel_data[channel_item]["channel_name"], 
            str(all_channel_data[channel_item]["channel_number"]), 
            all_channel_data[channel_item]["channel_description"],
            all_channel_data[channel_item]["channel_start"],
            all_channel_data[channel_item]["channel_end"],
            all_channel_data[channel_item]["channel_rules"]            # all_channel_data[channel_item]["templates"]
        )
        all_channels.append(channel)

    return all_channels

def schedule_by_tag_template(all_episodes, all_movies, all_commercials, block):
    # Set marker
    marker = block.start

    # Create and add slots until the end of the block
    while marker < block.end:
        # Get remaining time in block
        remaining_time_in_block = (block.end - marker).total_seconds()

        # Get a random media item that fits within remaining time of block
        random_media = random.sample([r for r in list(all_episodes + all_movies) if int(float(r.runtime)) <= remaining_time_in_block], 1)[0]

        logging.info(f"Working on time slot for {marker} - {random_media.name}")
        
        post_marker = marker + timedelta(seconds=int((random_media.runtime).split(".")[0]))
        logging.debug(f"Post marker: {post_marker}")

        # Define Program - Episode or Movie Object?
        if isinstance(random_media, Episode):
            logging.info(f"Random selection {random_media.name} is an episode")
            
            # Create Program
            program = Program(
                random_media.name, 
                random_media.show_name, 
                random_media.season_number, 
                random_media.episode_number, 
                random_media.overview,
                random_media.tags,
                random_media.runtime,
                random_media.filepath,
                marker,
                post_marker
            )
        if isinstance(random_media, Movie):
            logging.info(f"Random selection {random_media.name} is a movie")

            # Create Program
            program = Program(
                random_media.name, 
                None, 
                None, 
                None, 
                random_media.overview,
                random_media.tags,
                random_media.runtime,
                random_media.filepath,
                marker,
                post_marker
            )
        logging.info(program)

        # Create new slot
        logging.info("Creating new slot")
        new_slot = Slot(marker)

        # Create Slot Layout
        # Add program to slot layout
        new_slot.layout.append(program)
        new_slot.size = new_slot.determine_slot_size(program)
        new_slot.end = marker + timedelta(minutes=new_slot.size)
        # logging.info(f"Slot size: {new_slot.size}")
        # logging.info(f"Slot end: {new_slot.end}")

        # Update marker
        marker = post_marker

        # Fill slot with commercials until slot end
        new_slot.commtime = (new_slot.size * 60) - int(float(program.runtime))
        # logging.info(f"Comm time for slot: {new_slot.commtime}")
        while marker <= (new_slot.end - timedelta(seconds=15)):
            possible_commercials = [c for c in all_commercials if int(float(c.runtime)) <= new_slot.commtime]
            # logging.info(f"Found {len(possible_commercials)} commercials")
            if len(possible_commercials) > 0:
                comm = random.choice(possible_commercials)
                # logging.info(f"Chose {comm.filepath} - {comm.runtime}")
                post_marker = marker + timedelta(seconds=int(float(comm.runtime)))
                comm.start = marker
                comm.end = post_marker
                new_slot.layout.append(comm)

                # Update slot comm time and marker
                new_slot.commtime = new_slot.commtime - int(float(comm.runtime))
                marker = post_marker
            else:
                break

        # Fill remaining time with filler 
        # logging.info("Filling slot with filler")
        comm = [c for c in all_commercials if c.filepath == "/media/usb/bumpers/Filler/Midnight Television Vaporwave Mix Video.mp4"][0]
        comm.start = marker
        comm.end = new_slot.end
        new_slot.layout.append(comm)
        marker = post_marker

        # Append slot to block slots
        block.slots.append(new_slot)

        # Update marker
        marker = new_slot.end

        # Print Slot
        # new_slot.show_slot()

    return block

def schedule_by_ppv(movie):
    # Loop movie over with no commercials until it no longer fits
    block = Block(
        "PPV", 
        datetime.now().replace(hour=0, minute=0, second=0, microsecond=0),
        (datetime.now().replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)),
        None
    )

    marker = block.start
    remaining_time = timedelta(hours=24)
    movie_runtime = int(float(movie.runtime))
    while movie_runtime < (remaining_time).total_seconds():
        post_marker = marker + timedelta(seconds=movie_runtime)
        new_slot = Slot(marker)
        program = Program(movie.name, None, None, None, movie.overview, "movie", movie_runtime, movie.filepath, marker, post_marker)
        new_slot.layout.append(program)
        new_slot.end = post_marker
        block.slots.append(new_slot)
        remaining_time = remaining_time - timedelta(seconds=int(float(movie.runtime)))
        marker = post_marker

    

    logging.info(f"PPV: Remaining Time: {remaining_time}")



    return block



def create_schedule(channel):
    # Get all Episodes, Commercials and Movies from Catalog
    all_episodes = []
    all_commercials = []
    all_movies = []
    log.debug(f"\nFound {len(all_episodes)} raw episodes")
    log.debug(f"\nFound {len(all_commercials)} raw commercials\n")
    log.debug(f"\nFound {len(all_movies)} raw movies\n")

    for e in get_all_episodes_from_db():
        id, name, show_name, season_number, episode_number, overview, tags, runtime, filepath = e
        all_episodes.append(Episode(name, show_name, season_number, episode_number, overview, tags, runtime, filepath))

    for m in get_all_movies_from_db():
        id, name, overview, tvdb_id, tags, runtime, filepath = m
        all_movies.append(Movie(name, overview, tvdb_id, tags, runtime, filepath))

    for c in get_all_commercials_from_db():
        id, tags, runtime, filepath = c
        all_commercials.append(Commercial(tags, runtime, filepath))

    # Get all unique episode and movie tags
    all_tags = [t.tags for t in all_movies] + [t.tags for t in all_episodes]
    unique_tags = list(set([unique_tag for tag_str in all_tags for unique_tag in tag_str.split(",")]))

    # Define all blocks for channel schedule
    all_blocks = [
        {
            "name": "Morning",
            "start": datetime.today().replace(hour=5, minute=0, second=0, microsecond=0),
            "end": datetime.today().replace(hour=10, minute=0, second=0, microsecond=0)
        },
        {
            "name": "Midday",
            "start": datetime.today().replace(hour=10, minute=0, second=0, microsecond=0),
            "end": datetime.today().replace(hour=12, minute=0, second=0, microsecond=0)
        },
        {
            "name": "Afternoon",
            "start": datetime.today().replace(hour=12, minute=0, second=0, microsecond=0),
            "end": datetime.today().replace(hour=18, minute=0, second=0, microsecond=0)
        },
        {
            "name": "Primetime",
            "start": datetime.today().replace(hour=18, minute=0, second=0, microsecond=0),
            "end": datetime.today().replace(hour=22, minute=0, second=0, microsecond=0)
        },
        {
            "name": "LateNight",
            "start": datetime.today().replace(hour=22, minute=0, second=0, microsecond=0),
            "end": datetime.today().replace(hour=2, minute=0, second=0, microsecond=0) + timedelta(days=1)
        },
        {
            "name": "Overnight",
            "start": datetime.today().replace(hour=2, minute=0, second=0, microsecond=0) + timedelta(days=1),
            "end": datetime.today().replace(hour=5, minute=0, second=0, microsecond=0) + timedelta(days=1)
        },
    ]

    # PPV Rule
    if "PPV" in channel.templates:
        random_movie = random.choice(all_movies)
        channel.schedule.append(schedule_by_ppv(random_movie))
        channel.show_channel()
        return None

    # block_templates = ["ByTag", "MusicVideos", "Marathon", "PPV", "ShortWeb"]
    
    for block in all_blocks:
        # Randomly choose a block template
        block_template = random.choice(channel.templates)
        logging.info(f"Block {block['name']} has chosen {block_template} from {block['start']} to {block['end']}")

        # Create Block object
        current_block = Block(block["name"], block["start"], block["end"], block_template)

        # Schedule Block based on randomly chosen block template
        match block_template:
            case "ByTag":
                random_tags = random.sample(unique_tags, 3)
                random_tags = random_tags + ["tv"]
                logging.info(random_tags)

                # Filter episodes and movies based on tags
                filtered_episodes = [e for e in all_episodes if any(tag in e.tags for tag in random_tags)]
                filtered_movies = [m for m in all_movies if any(tag in m.tags for tag in random_tags)]
                logging.info(f"Scheduling by tag {random_tags}, using {len(filtered_episodes)} episodes and {len(filtered_movies)} movies")
                
                channel.schedule.append(schedule_by_tag_template(filtered_episodes, filtered_movies, all_commercials, current_block))
            case "MusicVideos":
                pass
            case "Marathon":
                pass
            case "PPV":
                pass
            case "ShortWeb":
                pass

    channel.show_channel_by_block()

def create_schedule2(channel):
    # Set flags
    ppv_channel = False
    if "PPV" in channel.name:
        ppv_channel = True

    # Get all Episodes, Commercials and Movies from Catalog
    all_episodes = []
    all_commercials = []
    all_movies = []
    log.debug(f"\nFound {len(all_episodes)} raw episodes")
    log.debug(f"\nFound {len(all_commercials)} raw commercials\n")
    log.debug(f"\nFound {len(all_movies)} raw movies\n")

    for e in get_all_episodes_from_db():
        id, name, show_name, season_number, episode_number, overview, tags, runtime, filepath = e
        all_episodes.append(Episode(name, show_name, season_number, episode_number, overview, tags, runtime, filepath))

    for m in get_all_movies_from_db():
        id, name, overview, tvdb_id, tags, runtime, filepath = m
        all_movies.append(Movie(name, overview, tvdb_id, tags, runtime, filepath))

    for c in get_all_commercials_from_db():
        id, tags, runtime, filepath = c
        all_commercials.append(Commercial(tags, runtime, filepath))

    # Get all unique episode and movie tags
    all_tags = [t.tags for t in all_movies] + [t.tags for t in all_episodes]
    unique_tags = list(set([unique_tag for tag_str in all_tags for unique_tag in tag_str.split(",")]))

    hour, minute = map(int, channel.start.split(":"))
    channel_start = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
    if channel.start == channel.end:
        channel_end = channel_start + timedelta(days=1)
    else:
        hour, minute = map(int, channel.end.split(":"))
        channel_end = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    logging.info(f"Channel {channel.name} - {channel_start}-{channel_end}")

    # Start Scheduling
    # marker = channel_start
    # while marker < channel_end:
        # Check to see if marker is in bounds of a channel rule
    for rule in channel.rules:
        hour, minute = map(int, rule["start"].split(":"))
        rule_start = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
        hour, minute = map(int, rule["end"].split(":"))
        rule_end = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
        new_block = Block(rule["name"], rule_start, rule_end, rule["tag_allow"])
        logging.info(f"New Block: {new_block.name}({new_block.tags}) - {new_block.start}-{new_block.end}\n")

        marker = rule_start
        while marker < rule_end:
            if "movie" in rule["media"]:
                movie = random.choice([m for m in all_movies if new_block.tags in m.tags])
                logging.info(f"Chose {movie.name}")

                # Create Slot
                new_slot = Slot()


        

for channel in import_channel_data():
    create_schedule2(channel)