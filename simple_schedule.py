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
import glob
import mpv

from http.server import HTTPServer, BaseHTTPRequestHandler
import json, socketserver, threading

# Logging settings
logging.basicConfig(
    level="DEBUG",
    format="%(message)s",
    datefmt="[%x]",
    handlers=[RichHandler(rich_tracebacks=True)]
)
log = logging.getLogger("rich")

# Load local env variables
load_dotenv()

# MPV
player = mpv.MPV(
    sub="no",
    vo="gpu",
    gpu_context="drm",
    hwdec="drm-copy",
    input_default_bindings=True,
    input_vo_keyboard=True,
    input_terminal=True,
    terminal="yes",
    input_ipc_server='0.0.0.0:6000'
)

# Global Vars
console = Console()
all_video_files = []
all_filler_files = []
# all_web_files = []
file_types = (".mp4", ".mkv")

# Goals
# - 1 Channel
# - Random mix of TV and Movies
# - After each playback, play random (3-8) commercials
# - Playlist method of playback
# - 
# - Buttons:
# - "Reset" - Without reboot
# - 
# - 

class MPVWebAPI(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/nowplaying":
            metadata = player.metadata or {}
            title = metadata.get('title') or player.filename or "Nothing playing"

            response = {
                "filename": player.filename,
                "path": player.path,
                "title": title,
                "paused": player.pause,
                "time_pos": player.time_pos,
                "duration": player.duration,
                "percent_pos": player.percent_pos,
                "playlist_pos": player.playlist_pos,
                "playlist_count": len(player.playlist)
            }

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps(response, indent=2).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == "/cmd":
            try:
                length = int(self.headers.get('Content-Length', 0))
                body = self.rfile.read(length)
                data = json.loads(body)
                command = data.get("command", [])
                if isinstance(command, str):
                    command = [command]
                

                # Execute MPV command
                if command[0] == "pause":
                    player.pause = not player.pause
                    result = {'success': True}
                elif "volume" in command[0]:
                    volume = int(command[0].split(" ")[1])
                    player.volume = volume
                    result = {'volume': volume}
                else:
                    result = player.command(*command)

                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"result": result}).encode())
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
        else:
            self.send_response(404)
            self.end_headers()

        if self.path == "/shutdown":
            try:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"status":"shutting down in 3 seconds"}')

                threading.Timer(3, lambda: os.system("sudo shutdown -h now")).start()
            except Exception as e:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(e)}).encode())
            


    def log_message(self, format, *args):
        return  # Silence server logs

# Start single HTTP server on port 8080
threading.Thread(
    target=lambda: HTTPServer(('0.0.0.0', 8080), MPVWebAPI).serve_forever(),
    daemon=True
).start()

log.info("Web API running → http://YOUR_PI_IP:8080/nowplaying  |  POST /cmd")

def Refill_Commercials():
    logging.debug("Refilling commercials")
    for ext in file_types:
        all_filler_files.extend(glob.glob(f"/media/usb/bumpers/**/*{ext}"))
    logging.debug(f"Filler now at {len(all_filler_files)}")
    random.shuffle(all_filler_files)
    return all_filler_files

def Refill_Media():
    logging.debug("Refilling media")
    for ext in file_types:
        all_video_files.extend(glob.glob(f"/media/usb/movies/**/*{ext}"))
        all_video_files.extend(glob.glob(f"/media/usb/tv/*/*/*{ext}"))
    logging.debug(f"Media now at {len(all_video_files)}")
    random.shuffle(all_video_files)
    return all_video_files

def Refill_Web_Media():
    logging.debug("Refilling Web Media")
    for ext in file_types:
        all_web_files.extend(glob.glob(f"/media/usb/web/*{ext}"))
    logging.debug(f"Web now at {len(all_web_files)}")
    random.shuffle(all_web_files)
    return all_web_files

def Generate_Schedule(all_filler_files, all_video_files):
    refilled = False

    # Build playlist
    while True:
        comm_number = random.randint(3,8)

        # Reload commercials
        if len(all_filler_files) < 10:
            all_filler_files = Refill_Commercials()
            if refilled:
                break
            refilled = True

        # Reload media
        if len(all_video_files) < 5:
            all_video_files = Refill_Media()
            if refilled:
                break
            refilled = True

        # Reload web
        # if len(all_web_files) < 2:
        #     all_web_files = Refill_Web_Media()


        logging.debug("Processing")
        comm_mark = 0
        while comm_mark < comm_number:
            player.playlist_append(all_filler_files[0])
            all_filler_files.pop(0)
            comm_mark += 1
        
        # Append movie/episode
        player.playlist_append(all_video_files[0])
        all_video_files.pop(0)


# Start HTTP server on port 8080
threading.Thread(target=lambda: HTTPServer(('0.0.0.0', 8080), IPCBridgeHandler).serve_forever(), daemon=True).start()

# Start server on port 8081
threading.Thread(target=lambda: HTTPServer(('0.0.0.0', 8081), Handler).serve_forever(), daemon=True).start()

overall = 0
all_filler_files = Refill_Commercials()
all_video_files = Refill_Media()
Generate_Schedule(all_filler_files, all_video_files)

for item in player.playlist:
    logging.debug(item)

player.playlist_pos = 0
while True:
    player.wait_for_playback()