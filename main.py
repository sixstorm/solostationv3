import scheduler
# import catalog
import mpv
import logging
from datetime import datetime, timedelta
from rich import print
from rich.logging import RichHandler
from rich.console import Console
from rich.table import Table
import time
import threading
import sys
import select
import termios
import tty
import uvicorn

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
                    if current_channel_number > 2:
                        current_channel_number = 1
                    channel_changed = True
                    # player.stop()
                    logging.info(f"Channel changed to {current_channel_number}")
                    time.sleep(0.2)
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

def run_fastapi():
    uvicorn.run("api:app", host="0.0.0.0", port=8000, log_level="info")

# Main Start
channel_changed = False

# Threads
threading.Thread(target=keyboard_listener, daemon=True).start()
threading.Thread(target=run_fastapi, daemon=True).start()

# Create schedule
# Import all channels from JSON
all_channels = scheduler.import_channel_data()

# Create schedule per channel
for channel in all_channels:
    logging.info(channel)
    logging.info(channel.schedule)
    scheduler.create_schedule(channel)
    scheduler.output_schedule(channel)
    # scheduler.show_schedule_table(channel.schedule)

# Main loop
while True:
    channel_changed = False
    logging.info("Starting main loop")

    while not channel_changed:
        now = datetime.now()

        # Get current Channel object
        current_channel = [channel for channel in all_channels if channel.channel_number == str(current_channel_number)][0]

        # Try and find the current slot
        try:
            current_slot = [slot for slot in current_channel.schedule if now >= slot.start and now <= slot.end][0]
            program = current_slot.program
            commercials = current_slot.commercials
        except Exception as e:
            print(f"Could not get current slot: {e}")
            time.sleep(2)
            continue

        current_slot.show_slot()

        # If current channel and slot are found, find what's playing now
        try:
            if program:
                if now >= program.start and now <= program.end:
                    playing_now = program
                    logging.info(f"Program {playing_now.name} should be playing now")
            else:
                if commercials:
                    playing_now = [c for c in commercials if now >= c.start and now <= c.end][0]
                    logging.info(f"Commercial {playing_now.filepath} should be playing now")
        except Exception as e:
            logging.info(f"Could not find playing_now: {e}")

        if playing_now:
            seek_time = (now - playing_now.start).total_seconds()

            # player.play(playing_now.filepath)
            player.command("loadfile", playing_now.filepath, "replace")
            player.start = int(seek_time)

            while now < playing_now.end and not channel_changed:
                now = datetime.now()
                time.sleep(0.1)
                if channel_changed:
                    break
    
    if channel_changed:
        continue