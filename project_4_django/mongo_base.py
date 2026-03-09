from pymongo import MongoClient
from django.conf import settings
import logging

print("🔥 MONGO FILE LOADED")
logger = logging.getLogger(__name__)

# Create client
mongo_uri = settings.MONGO_URI
mongo_host = settings.MONGO_HOST
mongo_port = settings.MONGO_PORT
mongo_user = settings.MONGO_USER
mongo_password = settings.MONGO_PASSWORD
mongo_db_name = settings.MONGO_DB_NAME

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