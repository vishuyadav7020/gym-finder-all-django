from pymongo import MongoClient
from django.conf import settings
import logging

print("🔥 MONGO FILE LOADED")
logger = logging.getLogger(__name__)

# Create client
mongo_uri = getattr(settings, "MONGO_URI", None)
mongo_host = getattr(settings, "MONGO_HOST", "mongodb")
mongo_port = getattr(settings, "MONGO_PORT", 27017)
mongo_user = getattr(settings, "MONGO_USER", None)
mongo_password = getattr(settings, "MONGO_PASSWORD", None)
mongo_db_name = getattr(settings, "MONGO_DB_NAME", "gym_finder_management_db")

if mongo_uri:
    logger.info("✅ Connecting to MongoDB ATLAS")
    client = MongoClient(mongo_uri)
else:
    logger.info(
        f"✅ Connecting to LOCAL MongoDB at "
        f"{mongo_host}:{mongo_port}"
    )
    kwargs = {
        "host": mongo_host,
        "port": mongo_port,
    }
    if mongo_user and mongo_password:
        kwargs["username"] = mongo_user
        kwargs["password"] = mongo_password
        kwargs["authSource"] = "admin"
    client = MongoClient(**kwargs)

# Database
db = client[mongo_db_name]
logger.info("✅ MongoDB connection initialized")