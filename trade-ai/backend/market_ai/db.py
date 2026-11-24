import os
import certifi
from motor.motor_asyncio import AsyncIOMotorClient

_mongo_url = os.environ["MONGO_URL"]
_db_name = os.environ["DB_NAME"]

client = AsyncIOMotorClient(
    _mongo_url,
    tls=True,
    tlsCAFile=certifi.where(),
)

db = client[_db_name]