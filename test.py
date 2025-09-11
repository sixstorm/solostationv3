# import tvdb_v4_official
# from dotenv import load_dotenv
# import os
# import json

# # Load local env variables
# load_dotenv()

# def connect_tvdb():
#     api_key = os.getenv("TVDB_API_KEY")
#     return tvdb_v4_official.TVDB(api_key)

# tvdb = connect_tvdb()

# tvdb.get_series_episodes(71663)

import uvicorn

def run_fastapi():
    uvicorn.run("api:app", host="0.0.0.0", port=8000, log_level="info")

run_fastapi()