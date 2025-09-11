from fastapi import FastAPI
import sqlite3
from dotenv import load_dotenv
import os
import random
from datetime import datetime

load_dotenv()

# SQLite Vars
conn = sqlite3.connect(os.getenv("CATALOG_DB"))
cursor = conn.cursor()

# FastAPI
app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hey Bro"}

@app.get("/all/allcommercials")
async def get_all_commercials():
    with sqlite3.connect(os.getenv("CATALOG_DB")) as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM COMMERCIALS"
        cursor.execute(query)
        commercials = cursor.fetchall()
        
        return commercials
    cursor.close()

@app.get("/random/randommovie")
async def get_random_movie():
    with sqlite3.connect(os.getenv("CATALOG_DB")) as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM MOVIES"
        cursor.execute(query)
        movies = cursor.fetchall()
        movie = random.choice(movies)

        return {"movie": movie}
    cursor.close()

@app.get("/randomepisode")
async def get_random_episode():
    with sqlite3.connect(os.getenv("CATALOG_DB")) as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM TV"
        cursor.execute(query)
        episode = random.choice(cursor.fetchall())
        
        return {"episode": episode}
    cursor.close()

@app.get("/random/randomcommercial")
async def get_random_commercial():
    with sqlite3.connect(os.getenv("CATALOG_DB")) as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM COMMERCIALS"
        cursor.execute(query)
        commercial = random.choice(cursor.fetchall())
        
        return {"commercial": commercial}
    cursor.close()

@app.get("/randomtvseries")
async def get_random_tv_series():
    with sqlite3.connect(os.getenv("CATALOG_DB")) as conn:
        cursor = conn.cursor()
        query = "SELECT ShowName FROM TV"
        cursor.execute(query)
        series = random.choice(cursor.fetchall())
        
        return {"series": series}
    cursor.close()

# @app.get("/playingnow")
# async def get_playing_now():
#     now = datetime.now()
#     query = "SELECT "