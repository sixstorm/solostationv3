import api
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

# SQLite Vars
conn = sqlite3.connect(os.getenv("CATALOG_DB"))
cursor = conn.cursor()

# Global vars
console = Console()
output_file = os.getenv("SCHEDULE_JSON")
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
        return f"{self.show_name}-{self.name} - S{self.season_number}E{self.episode_number}"

class Slot():
    def __init__(self, program, title=None):
        self.program = program
        self.start = program.start
        self.size = self.determine_slot_size()
        self.end = program.start + timedelta(minutes=self.size)
        self.title = self.program.tags
        self.commercials = []

        # Find commercial time within the Slot
        runtime_in_minutes = timedelta(minutes=(int(float(self.program.runtime)) / 60))
        self.commtime = (timedelta(minutes=self.size) - runtime_in_minutes).total_seconds()

    def create_layout(self, marker):
        # Create Slot layout
        self.slot_layout = []

        # Add program to layout
        logging.debug("Adding program to Slot layout")
        self.slot_layout.append(self.program)

        # Add commercials to layout
        # Set marker to the end of the program plus 1 second
        logging.debug("Adding commercials to Slot layout")
        marker = marker + timedelta(seconds=int(float(self.program.runtime))) ##+ timedelta(seconds=1)
        for comm in self.commercials:
            # Get end time for commercial
            comm_end_time = marker + timedelta(seconds=int(float(comm.runtime)))
            comm.start = marker
            comm.end = comm_end_time

            # If commercial does not exceed current Slot end time, add to Slot layout
            if comm_end_time < self.end:
                self.slot_layout.append(comm)
            else:
                # Append filler to Slot layout
                logging.debug(f"Commercial {comm.filepath} goes over current Slot end time of {self.end}")
                filler_end_time = self.end - timedelta(seconds=1)
                comm.start = marker
                comm.end = filler_end_time
                comm.filepath = "/media/usb/bumpers/Filler/Midnight Television Vaporwave Mix Video.mp4"
                self.slot_layout.append(comm)
                break

            # Move marker
            marker = marker + timedelta(seconds=int(float(comm.runtime)))


    def show_slot_layout(self):
        for layout in self.slot_layout:
            return f"{layout}"

    def show_slot(self):
        table = Table(title="Current slot")
        table.add_column("Show")
        table.add_column("Filepath")
        table.add_column("Start")
        table.add_column("End")

        for item in self.slot_layout:
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


    def determine_slot_size(self):
        runtime = int(float(self.program.runtime))
        match runtime:
            case _ if (runtime / 60) < 30:
                return 30
            case _ if (runtime / 60) > 30 and (runtime / 60) < 60:
                return 60

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
        return f"Slot: {self.title}  Show: {self.program.show_name} - {self.start} - {self.end} - {self.size} - {self.commtime}"

class Block():
    def __init__(self, name, start, end, tags=[]):
        self.name = name
        self.start = start
        self.end = end
        self.tags = tags
        self.slots = []

    def add_slot(self, slot):
        self.slots.append(slot)

class Channel():
    def __init__(self, channel_name, channel_number, channel_description, templates):
        self.channel_name = channel_name
        self.channel_number = channel_number
        self.channel_description = channel_description
        self.templates = templates
        self.schedule = []

    def __str__(self):
        return f"Channel {self.channel_name} - {self.channel_number} - {self.channel_description}"


def get_all_episodes_from_db():
    with sqlite3.connect(os.getenv("CATALOG_DB")) as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM TV"
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
            all_channel_data[channel_item]["templates"]
        )
        all_channels.append(channel)

    return all_channels

def create_schedule(channel):
    # Get all Episodes and Commercials from Catalog
    all_episodes_raw = get_all_episodes_from_db()
    log.debug(f"\nFound {len(all_episodes_raw)} raw episodes")
    all_commercials_raw = get_all_commercials_from_db()
    log.debug(f"\nFound {len(all_commercials_raw)} raw commercials\n")
    # all_movies_raw = get_all_movies_from_db()
    # log.debug(f"\nFound {len(all_movies_raw)} raw movies\n")

    all_episodes = []
    all_commercials = []
    all_movies = []

    for e in all_episodes_raw:
        id, name, show_name, season_number, episode_number, overview, tags, runtime, filepath = e
        all_episodes.append(Episode(name, show_name, season_number, episode_number, overview, tags, runtime, filepath))

    for c in all_commercials_raw:
        id, tags, runtime, filepath = c
        all_commercials.append(Commercial(tags, runtime, filepath))

    log.debug(f"\nI see {len(all_episodes)} episodes in Class form")
    log.debug(f"\nI see {len(all_commercials)} episodes in Class form\n")

    # Shuffle all episodes and commercials
    random.shuffle(all_episodes)
    random.shuffle(all_commercials)

    # Create schedule
    # Fill all blocks
    all_blocks = ["Morning", "Midday", "Afternoon", "Primetime", "LateNight", "Overnight"]
    for block in all_blocks:
        new_slots = []
        tags = ["comedy"]
        start_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start_time_fmt = datetime.strftime(start_time, "%Y-%m-%d %H:%M:%s")
        end_time = (start_time + timedelta(days=1)).replace(second=0, microsecond=0)
        end_time_fmt = datetime.strftime(end_time, "%Y-%m-%d %H:%M:%s")
        marker = start_time
        current_block = Block(block, start_time, end_time, tags)
        log.info(f"Starting schedule at {start_time_fmt}, ending at {end_time_fmt}")

        # Create and add slots until end_time
        while marker < end_time:
            # Get first shuffled episode
            episode = all_episodes[0]
            post_marker = marker + timedelta(seconds=int((episode.runtime).split(".")[0]))

            # Create Program
            program = Program(
                episode.name, 
                episode.show_name, 
                episode.season_number, 
                episode.episode_number, 
                episode.overview,
                episode.tags,
                episode.runtime,
                episode.filepath,
                marker,
                post_marker)
            log.debug(f"Adding {program.show_name}-{program.name} to the schedule at {marker} for {program.start}")

            # Create a Slot
            new_slot = Slot(program)

            # Add commercials that fit
            total_comm_time = new_slot.commtime

            # If more than 15 seconds is available in the Slot
            while total_comm_time >= 15:
                logging.debug(f"Attempting to find commercials under {total_comm_time} seconds")
                possible_commercials = [c for c in all_commercials if int(float(c.runtime)) <= new_slot.commtime]
                if possible_commercials:
                    # Chose random commercial and append to Slot commercial list
                    pc = random.choice(possible_commercials)
                    new_slot.commercials.append(pc)

                    # Update commercial time
                    total_comm_time = total_comm_time - int(float(pc.runtime))
                else:
                    break

            # Create Slot layout
            new_slot.create_layout(marker)

            # Append new Slot
            new_slots.append(new_slot)
            logging.debug(new_slot)

            marker = marker + timedelta(minutes=new_slot.size)
            logging.debug(f"Marker now at {marker}")

            all_episodes.pop(0)

        channel.schedule = new_slots

def output_schedule(channel):
    for Slot in channel.schedule:
        # Program        
        with sqlite3.connect(os.getenv("CATALOG_DB")) as conn:
            cursor = conn.cursor()
            # cursor.execute(query)
            cursor.execute(
                "INSERT INTO SCHEDULE (ChannelNumber, Name, ShowName, Season, Episode, Overview, Tags, Runtime, Filepath, Start, End) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    channel.channel_number,
                    Slot.program.name,
                    Slot.program.show_name,
                    Slot.program.season_number,
                    Slot.program.episode_number,
                    Slot.program.overview,
                    Slot.program.tags,
                    Slot.program.runtime,
                    Slot.program.filepath,
                    Slot.program.start,
                    Slot.program.end
                ),
            )
            conn.commit()
        cursor.close()
        
        # Commercials        
        with sqlite3.connect(os.getenv("CATALOG_DB")) as conn:
            cursor = conn.cursor()
            # cursor.execute(query)
            cursor.execute(
                "INSERT INTO SCHEDULE (ChannelNumber, Name, ShowName, Season, Episode, Overview, Tags, Runtime, Filepath, Start, End) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    channel.channel_number,
                    Slot.program.name,
                    Slot.program.show_name,
                    Slot.program.season_number,
                    Slot.program.episode_number,
                    Slot.program.overview,
                    Slot.program.tags,
                    Slot.program.runtime,
                    Slot.program.filepath,
                    Slot.program.start,
                    Slot.program.end
                ),
            )
            conn.commit()
        cursor.close()

def output_schedule_json(scheduled_slots):
    # List of slots
    output_json = []

    for Slot in scheduled_slots:
        # Output to JSON
        commercial_json = [
            {
                "tags": item.tags,
                "runtime": item.runtime,
                "filepath": item.filepath
            }
            for item in Slot.commercials
        ]

        slot_json = {
            "program": {
                "name": Slot.program.name, 
                "show_name": Slot.program.show_name, 
                "season_number": Slot.program.season_number,
                "episode_number": Slot.program.episode_number,
                "overview": Slot.program.overview,
                "tags": Slot.program.tags,
                "runtime": Slot.program.runtime,
                "filepath": Slot.program.filepath,
                "start": datetime.strftime(Slot.program.start, "%Y-%m-%d %H:%M:%S"),
                "end": datetime.strftime(Slot.program.end, "%Y-%m-%d %H:%M:%S")
            },        
            "start": datetime.strftime(Slot.start, "%Y-%m-%d %H:%M:%S"),
            "end": datetime.strftime(Slot.end, "%Y-%m-%d %H:%M:%S"),
            "size": Slot.size,
            "title": Slot.title,
            "commercials": commercial_json,
        }
        output_json.append(slot_json)


    with open(output_file, "w") as file:
        json.dump(output_json, file, indent=4)