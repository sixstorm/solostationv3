import scheduler_v4
import mpv
import logging
import time
import sqlite3
import os
import threading
import sys
import select
import termios
import tty
from dotenv import load_dotenv
from datetime import datetime
from rich.logging import RichHandler
from rich.console import Console

# Logging settings
logging.basicConfig(
    level="DEBUG",
    format="%(message)s",
    datefmt="[%x]",
    handlers=[RichHandler(rich_tracebacks=True)]
)
log = logging.getLogger("rich")

# MPV
player = mpv.MPV(
    sub="no",
    vo="gpu",
    hwdec="drm-copy"
)

# Global Vars
console = Console()
current_channel_number = 1
load_dotenv()

# Functions
def keyboard_listener():
    global current_channel_number, channel_changed
    old_settings = termios.tcgetattr(sys.stdin)
    tty.setcbreak(sys.stdin.fileno())
    try:
        while True:
            r, _, _ = select.select([sys.stdin], [], [], 0.01)
            if r:
                key = sys.stdin.read(1)
                if key == "s":
                    current_channel_number += 1
                    if current_channel_number > 6:
                        current_channel_number = 1
                    channel_changed = True

                    logging.info(f"Channel changed to {current_channel_number}")
                    clear_osd_text()
                    time.sleep(0.2)
                if key == "w":
                    current_channel_number -= 1
                    if current_channel_number == 0:
                        current_channel_number = 6
                    channel_changed = True

                    logging.info(f"Channel changed to {current_channel_number}")
                    clear_osd_text()
                    time.sleep(0.2)
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

def update_osd_text(player, text, font_name="Arial"):
    overlay_id = 0
    ass_text = "{\\an1\\fs30\\b1\\alpha&H80&\\fn" + font_name + "}" + text.replace("\\", "\\\\")
    try:
        player.command("osd-overlay", overlay_id, "ass-events", ass_text)
        log.debug(f"OSD updated with: {text} using font: {font_name}")
    except mpv.MPVError as e:
        log.info(f"MPV OSD error: {e} - Command: osd-overlay {overlay_id} ass-events {ass_text}")
        raise

def clear_osd_text():
    player.command("osd-overlay", 0, "none", "")

def get_schedule(channel_number):
    schedule = []
    with sqlite3.connect(os.getenv("SCHEDULE_DB")) as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT * FROM SCHEDULE WHERE ChannelNumber = {channel_number}"
        )
        results = cursor.fetchall()
        for result in results:
            ID, channel_number, name, show_name, season_number, episode_number, overview, tags, runtime, filepath, start, end = result
            schedule.append({
                "channel_number": channel_number,
                "name": name,
                "show_name": show_name,
                "season_number": season_number,
                "episode_number": episode_number,
                "overview": overview,
                "tags": tags,
                "runtime": runtime,
                "filepath": filepath,
                "start": start,
                "end": end
            })

    conn.close()
    return schedule

def check_schedule(channel_number):
    today = datetime.now().date()
    start_of_day = datetime.combine(today, datetime.min.time())
    end_of_day = datetime.combine(today, datetime.max.time())
    # logging.info(f"{start_of_day=} - {end_of_day=}")

    with sqlite3.connect(os.getenv("SCHEDULE_DB")) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM SCHEDULE
            WHERE ChannelNumber = ?
              AND start >= ?
              AND start <= ?
            """,
            (channel_number, start_of_day.strftime("%Y-%m-%d %H:%M:%S"), end_of_day.strftime("%Y-%m-%d %H:%M:%S"))
        )
        result = cursor.fetchone()[0]
        logging.debug(f"Result from schedule check: {result}")

    return result > 0

def convert_dt(time_str):
    return datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")

# def on_event(event):
#     if event["event"] == "file-loaded":
#         seek_time = (now - convert_dt(playing_now["start"])).total_seconds()
#         logging.debug(f"Seeking {seek_time}s")
#         player.seek(int(seek_time), "absolute")

# Threads
threading.Thread(target=keyboard_listener, daemon=True).start()

# Main
force_schedule_clear = True

# Clear schedule in DB and create new
for channel in scheduler_v4.import_channel_data():
    scheduler_v4.initialize_schedule_db()
    if force_schedule_clear:
        scheduler_v4.clear_schedule_table()
    schedule_check = check_schedule(channel.number)
    logging.debug(f"Schedule check for channel {channel.number}: {schedule_check}")
    if not schedule_check:
        scheduler_v4.create_schedule(channel)

# while True:
#     channel_changed = False
#     schedule = get_schedule(current_channel_number)

#     while not channel_changed:
#         now = datetime.now()

#         # Build playlist
#         # Find current slot
#         playing_now = [i for i in schedule if now >= convert_dt(i["start"]) and now <= convert_dt(i["end"])][0]
#         logging.info(f"Currently playing: {playing_now['name']}\tStart: {playing_now['start']}\tEnd: {playing_now['end']}")    
#         playing_now_index = schedule.index(playing_now)

#         # Build playlist from playing_now to end of schedule        
#         for item in schedule[playing_now_index:]:
#             player.playlist_append(item["filepath"])

#         # Set MPV at beginning of playlist
#         logging.debug("Setting position at 0")
#         player.playlist_pos = 0

#         # Load file and wait for property "duration" to be available
#         player.command("loadfile", playing_now["filepath"], "replace")
#         player.wait_for_property("duration")

#         # Get seek time and seek
#         seek_time = (now - convert_dt(playing_now["start"])).total_seconds()
#         logging.debug(f"Seeking {seek_time}s")
#         player.time_pos = int(seek_time)

#         # Show channel number
#         update_osd_text(player, f"{current_channel_number}")

#         # Main playback loop
#         while now < convert_dt(playing_now["end"]) and not channel_changed:
#             now = datetime.now()
#             time.sleep(0.1)
#             if channel_changed:
#                 break
