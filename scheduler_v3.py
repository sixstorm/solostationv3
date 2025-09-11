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

    def fill_commercials(self, all_commercials, tolerance=5, min_padding=5, max_padding=25):
        marker = self.content.end
        logging.debug(f"Fill Commercial Begin - CTT: {self.comm_time_total} - Marker: {marker}")

        while self.comm_time_total > max_padding:
            # Get all commercials that fit under comm_total_time + tolerance
            candidates = [
                c for c in all_commercials
                if int(float(c.runtime)) <= self.comm_time_total + tolerance
            ]

            logging.debug(f"Found {len(candidates)} candidates for {self.comm_time_total} seconds remaining")

            # Select and add commercial to lineup
            commercial = random.choice(candidates)
            runtime = int(float(commercial.runtime))
            logging.debug(f"Chose commercial with {runtime} runtime")
            commercial.start = marker
            commercial.end = marker + timedelta(seconds=runtime)
            self.commercials.append(commercial)

            self.comm_time_total -= runtime
            marker = commercial.end
            logging.debug(f"Post commercial add - Marker: {marker} - CTT: {self.comm_time_total}")

        # Final commercial - Best fit
        if self.comm_time_total > 0:
            best = None
            best_diff = float("inf")
            for c in all_commercials:
                runtime = int(float(c.runtime))
                diff = abs(self.comm_time_total - runtime)
                if diff < best_diff and runtime <= self.comm_time_total + tolerance:
                    best = c
                    best_diff = diff
            if best:
                runtime = int(float(best.runtime))
                best.start = marker
                best.end = marker + timedelta(seconds=runtime)
                self.commercials.append(best)
                marker = best.end
                self.comm_time_total -= runtime
                logging.debug(f"Best fit commercial for {runtime} - Overshoot: {abs(self.comm_time_total)}")
        
        logging.info(f"Slot has ended at {marker}")

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
    def __init__(self, name, number, description):
        self.name = name
        self.number = number
        self.description = description
        self.schedule = []

    def print_as_table(self):
        table = Table(title="Channel Schedule")
        table.add_column("Slot Start")
        table.add_column("Slot End")
        table.add_column("Start")
        table.add_column("End")
        table.add_column("Filepath")

        for block in self.schedule:
            for slot in block["strategy"]:
                table.add_row(
                    datetime.strftime(slot.start, "%Y-%m-%d %H:%M:%S"),
                    datetime.strftime(slot.end, "%Y-%m-%d %H:%M:%S"),
                    datetime.strftime(slot.content.start, "%Y-%m-%d %H:%M:%S"),
                    datetime.strftime(slot.content.end, "%Y-%m-%d %H:%M:%S"),
                    slot.content.filepath
                )
        
        console.print(table)


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

    def generate_slots(self, start, duration):
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
            chosen_episode = chosen_episodes[0]
            runtime = int(float(chosen_episode.runtime))
            chosen_episode.start = marker
            chosen_episode.end = marker + timedelta(seconds=runtime)
            slot = Slot(marker, chosen_episode)
            logging.info(f"Choosing episode {chosen_episode.name} - End: {chosen_episode.end} - Size: {slot.size} - TCT: {slot.comm_time_total}")

            # Add commercials post episode
            all_commercials = [c for c in self.all_content if c.type == "commercial"]
            logging.info(f"All commercials: {len(all_commercials)}")
            marker = slot.fill_commercials(all_commercials)

            # Append slot to slots
            slots.append(slot)
            total += timedelta(minutes=slot.size)
            chosen_episodes.pop(0)
            # slot.print_as_table()
        
        return slots, marker

class MovieTagStrategy:
    def __init__(self, all_content, tags):
        self.all_content = all_content
        self.tags = random.sample(tags, 2)
        # self.media = [m for m in [i for i in all_content if i.type == 'movie'] if self.tags in m.tags]
        self.media = self.filter_content([m for m in all_content if m.type == 'movie'])
        logging.info(f"Found {len(self.media)} media items")

    def filter_content(self, media):
        movies = [m for m in media if [t for t in self.tags if t in m.tags]]
        return movies

    def determine_next_start(self, content_end):
        pass

    def generate_slots(self, start, duration):
        logging.info(f"Tag Run: {self.tags}")
        slots = []
        marker = start
        total = timedelta()

        while total < duration:
            # Prepare chosen Content and create the Slot
            random_media = self.media[0]
            runtime = int(float(random_media.runtime))
            random_media.start = marker
            random_media.end = marker + timedelta(seconds=runtime)
            slot = Slot(marker, random_media)
            logging.info(f"Chose {random_media.name} - End: {random_media.end} - Size: {slot.size}")

            # Append commercials
            all_commercials = [c for c in self.all_content if c.type == "commercial"]
            marker = slot.fill_commercials(all_commercials)

            # Finalize Slot
            slots.append(slot)
            marker = slot.end
            total += timedelta(seconds=int(float(random_media.runtime)))
            self.media.pop(0)

        return slots, marker

class Strategy:
    def __init__(self, all_content):
        self.all_content = all_content
        self.media = [c for c in all_content if c.type != 'commercial']

    def generate_slots(self, start, duration):
        slots = []
        marker = start
        total = timedelta()

        while total < duration:
            # Update time_remaining
            time_remaining = duration - total

            # Get all media with a runtime under time_remaining
            random_media = [m for m in self.media if timedelta(seconds=int(float(m.runtime))) <= time_remaining]
            logging.info(f"Found {len(random_media)} media items under {time_remaining} - Total: {total}")
            if not random_media:
                # Find filler content
                random_media = [self.find_filler(time_remaining, marker)]

            # Shuffle and randomly choose media
            random.shuffle(random_media)
            chosen_content = random_media[0]

            # Prepare chosen Content and create the Slot
            runtime = int(float(chosen_content.runtime))
            chosen_content.start = marker
            chosen_content.end = marker + timedelta(seconds=runtime)
            slot = Slot(marker, chosen_content)

            # Add commercials
            all_commercials = [c for c in self.all_content if c.type == "commercial"]
            logging.info(f"All commercials: {len(all_commercials)}")
            marker = slot.fill_commercials(all_commercials)

            # Append Slot to slots and pop Content from list
            # marker = slot.end
            slots.append(slot)
            total += timedelta(minutes=slot.size)
            self.media.pop(0)

        return slots, marker

    def find_filler(self, time_remaining, marker):
        best = None
        best_diff = float("inf")
        for m in self.media:
            runtime = int(float(m.runtime))
            diff = abs(time_remaining - runtime)
            if diff < best_diff and runtime <= time_remaining:
                best = m
                best_diff = diff

        return best





# Functions
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

def clear_schedule_table():
    with sqlite3.connect(os.getenv("CATALOG_DB")) as conn:
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
            all_channel_data[channel_item]["channel_description"]        # all_channel_data[channel_item]["templates"]
        )
        all_channels.append(channel)

    return all_channels

def export_schedule(channel):
    with sqlite3.connect(os.getenv("CATALOG_DB")) as conn:
        cursor = conn.cursor()

        for block in channel.schedule:
            for slot in block:
                # Insert content into schedule
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
                            datetime.strftime(slot.content.start, "%Y-%m-%d %H:%M:%S"),
                            datetime.strftime(slot.content.end, "%Y-%m-%d %H:%M:%S")
                        )
                    )
                    conn.commit()

        
    cursor.close()


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
    unique_tags = list(set([unique_tag for tag_str in all_tags for unique_tag in tag_str.split(",") if tag_str != "commercial"]))

    # Set channel marker to track through the day
    all_strategies = ["TVMarathon", "MoviesByTag", "Basic"]
    # all_strategies = ["Basic", "MoviesByTag"]
    channel_marker = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    channel_end = channel_marker + timedelta(days=1)

    # Go through day and fill via random strategies
    while channel_marker < channel_end:
        # Select a random number of hours for a block
        random_strategy = random.choice(all_strategies)
        logging.info(f"Choosing {random_strategy} strategy")
        block_duration = timedelta(hours=random.randint(3, 5))
        hours_remaining = (channel_end - channel_marker).total_seconds() / 60 / 60
        logging.info(f"There are {hours_remaining} hours left in the day")
        if block_duration > timedelta(hours=hours_remaining):
            block_duration = timedelta(hours=hours_remaining)
            time_remaining = (channel_end - channel_marker).total_seconds()
            logging.info(f"Using FillInStrategy to fill {block_duration} hours")
            strategy, channel_marker = Strategy(all_content).generate_slots(channel_marker, block_duration)
            block = { "start": channel_marker, "strategy": strategy }
            channel.schedule.append(block)
            break
        logging.info(f"Chose {block_duration} hours for this block - {channel_marker}")

        match random_strategy:
            case "TVMarathon":
                strategy, channel_marker = TVMarathonStrategy(all_content).generate_slots(channel_marker, block_duration)
                block = { "start": channel_marker, "strategy": strategy, "channel_number": channel.number }
            case "MoviesByTag":
                strategy, channel_marker = MovieTagStrategy(all_content, unique_tags).generate_slots(channel_marker, block_duration)
                block = { "start": channel_marker, "strategy": strategy, "channel_number": channel.number }
            case "Basic":
                strategy, channel_marker = Strategy(all_content).generate_slots(channel_marker, block_duration)
                block = { "start": channel_marker, "strategy": strategy, "channel_number": channel.number }

        # Append block to channel schedule
        channel.schedule.append(block)

    channel.print_as_table()
    export_schedule(channel)
    

    # print_schedule(channel.schedule)

# Script Start
clear_schedule_table()
for channel in import_channel_data():
    create_schedule(channel)