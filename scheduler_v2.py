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
import subprocess
import tempfile
import glob

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
    def __init__(self, start, content):
        self.start = start
        self.content = content
        self.size = self.determine_slot_size()
        self.end = self.start + timedelta(minutes=self.size)
        # self.end = self.start + timedelta(seconds=int(float(content.runtime)))
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

    def fill_commercials(self, all_commercials):
        marker = self.content.end
        logging.info(f"Marker at Fill Commercial Begin: {marker}")
        while self.comm_time_total > 15:
            # Get all commercials that fit under comm_total_time
            commercial = random.choice([c for c in all_commercials if int(float(c.runtime)) < self.comm_time_total])
            commercial.start = marker
            commercial.end = marker + timedelta(seconds=int(float(commercial.runtime)))
            self.commercials.append(commercial)
            self.comm_time_total -= int(float(commercial.runtime))
            marker = commercial.end
            logging.info(f"Marker post commercial add: {marker}")
        
        # Filler
        # logging.info(f"Filler insert - Marker: {marker} - Slot.End - {self.end}")
        # filler = [c for c in all_commercials if c.filepath == "/media/usb/bumpers/Filler/Midnight Television Vaporwave Mix Video.mp4"][0]
        # filler.start = marker
        # filler.end = self.end
        # self.commercials.append(filler)

        return marker

    def print_as_table(self):
        table = Table(title="Slot")

        table.add_column("Size")
        table.add_column("Start")
        table.add_column("End")
        table.add_column("Name")
        table.add_column("Type")
        table.add_column("Overview")
        table.add_column("TVDB_ID")
        table.add_column("Tags")
        table.add_column("Runtime")
        table.add_column("Filepath")

        if self.content.type == "tv":
            table.add_row(
                str(self.size), 
                str(self.start), 
                str(self.end), 
                self.content.name, 
                self.content.type, 
                self.content.overview, 
                self.content.tvdb_id, 
                self.content.tags, 
                self.content.runtime, 
                self.content.filepath
            )
        else:
            table.add_row(
                str(self.size), 
                str(self.start), 
                str(self.end), 
                self.content.name, 
                self.content.type, 
                self.content.overview, 
                self.content.tvdb_id, 
                self.content.tags, 
                self.content.runtime, 
                self.content.filepath
            )

        for commercial in self.commercials:
            table.add_row(
                None,
                str(commercial.start), 
                str(commercial.end), 
                commercial.name, 
                commercial.type,
                None,
                None, 
                commercial.tags, 
                str(commercial.runtime), 
                commercial.filepath
            )

        console.print(table)

class Channel:
    def __init__(self, name, number, description, schedule=None):
        self.name = name
        self.number = number
        self.description = description

class PPVStrategy:
    def __init__(self, all_content, movie=None):
        self.movie = random.choice([c for c in all_content if c.type == "movie"])

    def generate_slots(self, start, duration=timedelta(hours=24)):
        slots = []
        marker = start
        total = timedelta()

        while total < duration:
            slot = Slot(marker, self.movie)
            slots.append(slot)
            marker = slot.end
            total += timedelta(seconds=int(float(self.movie.runtime)))

        return slots

    def __str__(self):
        logging.info(f"Name: {self.movie.name}")

class TVMarathonStrategy:
    def __init__(self, all_content, series=None, episodes=None):
        self.all_content = all_content
        self.series = random.choice([s.show_name for s in all_content if s.type == 'tv' and s.show_name])
        self.episodes = [e for e in [s for s in all_content if s.type == 'tv'] if e.show_name == self.series]

    def generate_slots(self, start, duration=timedelta(hours=1)):
        logging.debug(f"TV Marathon for Series {self.series}")
        slots = []
        marker = start
        total = timedelta()

        # Sort episodes by Season and Episode Numbers
        sorted_episodes = sorted(self.episodes, key=lambda x: (int(x.season_number), int(x.episode_number)))

        # Pick a random episode and get the next 20 number of leading episodes
        starting_episode = random.choice(sorted_episodes)
        starting_episode_index = sorted_episodes.index(starting_episode)
        chosen_episodes = sorted_episodes[starting_episode_index:starting_episode_index+20]

        # Fill slots
        while total < duration:
            # Fill Content metadata
            chosen_episodes[0].start = marker
            chosen_episodes[0].end = marker + timedelta(seconds=int(float(chosen_episodes[0].runtime)))
            slot = Slot(marker, chosen_episodes[0])
            logging.info(f"Choosing episode {chosen_episodes[0].name} - End: {chosen_episodes[0].end} - Size: {slot.size} - TCT: {slot.comm_time_total}")

            # Create dynamic bumper
            bumper = Content(
                f"bumper-{datetime.strftime(slot.start, '%H-%M')}",
                "bumper",
                None,
                None,
                None,
                5, 
                create_bumper(chosen_episodes[0])
            )
            logging.info(f"Created bumper: {bumper.filepath}")
            time.sleep(1)

            # Add commercials post episode
            all_commercials = [c for c in self.all_content if c.type == "commercial"]
            logging.info(f"All commercials: {len(all_commercials)}")
            slot_marker = slot.fill_commercials(all_commercials)

            # Add bumper
            bumper.start = slot_marker
            bumper.end = slot.end
            slot.commercials.append(bumper)

            # Append slot to slots
            slots.append(slot)
            marker = marker + timedelta(minutes=slot.size)# slot.end
            total += timedelta(minutes=slot.size)
            chosen_episodes.pop(0)
            slot.print_as_table()
            # time.sleep(.5)
        
        return slots

class TagStrategy:
    def __init__(self, all_content, tags):
        self.tags = random.sample(tags, 1)[0]
        self.media = [m for m in [i for i in all_content if i.type == 'movie'] if self.tags in m.tags]

    def generate_slots(self, start, duration=timedelta(hours=6)):
        slots = []
        marker = start
        total = timedelta()

        logging.info(f"Chose tag(s) {self.tags}")
        while total < duration:
            slot = Slot(marker, self.media[0])
            slots.append(slot)
            marker = slot.end
            total += timedelta(seconds=int(float(self.media[0].runtime)))
            self.media.pop(0)

        return slots

class Strategy:
    def __init__(self, all_content):
        self.media = random.sample(all_content, 100)
        self.all_content = all_content

    def generate_slots(self, start, duration=timedelta(hours=3)):
        slots = []
        marker = start
        total = timedelta()

        while total < duration:
            logging.info(f"Inserting {self.media[0]}")
            self.media[0].start = marker
            self.media[0].end = marker + timedelta(seconds=int(float(self.media[0].runtime)))
            slot = Slot(marker, self.media[0])
            marker = slot.end
            total += timedelta(seconds=int(float(self.media[0].runtime)))

            # Create dynamic bumper
            bumper = Content(
                f"bumper-{datetime.strftime(slot.start, '%H-%M')}",
                "bumper",
                None,
                None,
                None,
                5, 
                create_bumper(self.media[0])
            )

            # Add commercials post episode
            all_commercials = [c for c in self.all_content if c.type == "commercial"]
            logging.info(f"All commercials: {len(all_commercials)}")
            slot_marker = slot.fill_commercials(all_commercials)

            # Add bumper
            bumper.start = slot_marker
            bumper.end = slot.end
            slot.commercials.append(bumper)

            slots.append(slot)
            self.media.pop(0)

        return slots


# Functions
def create_bumper(content):
    if hasattr(content, 'show_name'):
        text = f"Up Next: {content.show_name}"
    else:
        text = f"Up Next: {content.name}"

    with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
        f.write(text.encode("utf-8"))
        textfile = f.name

    cmd = [
        "ffmpeg", "-y",
        "-stream_loop", "-1", "-i", "backgroundvideo.mp4",
        "-t", "5",
        "-vf",
        f"drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf:"
        f"textfile={textfile}:fontcolor=white:fontsize=48:"
        f"x=(w-text_w)/2:y=h-100:shadowcolor=black:shadowx=2:shadowy=2",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-an", f"./bumpers/{datetime.strftime(content.start, '%H-%M')}.mp4"
    ]

    subprocess.run(cmd, check=True)
    os.unlink(textfile)
    return f"{datetime.strftime(content.start, '%H-%M')}.mp4"

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
            all_channel_data[channel_item]["channel_description"]        # all_channel_data[channel_item]["templates"]
        )
        all_channels.append(channel)

    return all_channels

def print_schedule(schedule):
    table = Table(title="Schedule")
    table.add_column("Slot Start")
    table.add_column("Slot End")
    table.add_column("Start")
    table.add_column("End")
    table.add_column("Series")
    table.add_column("Name")
    table.add_column("Type")
    # table.add_column("Overview")
    table.add_column("Tags")
    table.add_column("Runtime")
    table.add_column("Filepath")

    for block in schedule:
        for slot in block["strategy"]:
            slot.print_as_table()
            time.sleep(1)

        #     table.add_row(
        #         str(slot.start), 
        #         str(slot.end), 
        #         datetime.strftime(slot.content.start, "%Y-%m-%d %H:%M:%S"),
        #         datetime.strftime(slot.content.end, "%Y-%m-%d %H:%M:%S"),
        #         slot.content.name, 
        #         slot.content.type, 
        #         # slot.content.overview, 
        #         slot.content.tvdb_id, 
        #         slot.content.tags, 
        #         slot.content.runtime, 
        #         slot.content.filepath,
        #     )

        #     # Commercials
        #     for commercial in slot.commercials:
        #         table.add_row(
        #             None,
        #             None,
        #             datetime.strftime(commercial.start, "%Y-%m-%d %H:%M:%S"),
        #             datetime.strftime(commercial.end, "%Y-%m-%d %H:%M:%S"),
        #             None,
        #             "commercial",
        #             # None,
        #             None,
        #             None,
        #             commercial.runtime,
        #             commercial.filepath
        #         )
        # console.print(table)


def create_schedule(channel):
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
    unique_tags = list(set([unique_tag for tag_str in all_tags for unique_tag in tag_str.split(",")]))

    # Define blocks for the day randomly
    channel.schedule = [
        # {"start": "00:00", "duration": 2*60, "strategy": TVMarathonStrategy(all_content).generate_slots(datetime.now().replace(hour=0, minute=0, second=0, microsecond=0))},
        {"start": "00:00", "duration": 6*60, "strategy": Strategy(all_content).generate_slots(datetime.now().replace(hour=5, minute=0, second=0, microsecond=0))},
        # {"start": "00:00", "duration": 24*60, "strategy": PPVStrategy(all_content).generate_slots(datetime.now().replace(hour=11, minute=0, second=0, microsecond=0))}
    ]

    # print_schedule(channel.schedule)

# Script Start
# Clear out Bumper folder
bumper_files = glob.glob("/bumpers/*.mp4")
for file in bumper_files:
    logging.info(f"Removing {file}")
    os.remove(file)

for channel in import_channel_data():
    create_schedule(channel)