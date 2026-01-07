import json
import os

import dotenv
from sqlalchemy import Table, create_engine, MetaData, Column, VARCHAR, BOOLEAN, DateTime

dotenv.load_dotenv()

DATABASE_URL = os.getenv('DATABASE_URL') or 'sqlite:///data/collabmarkov.db'
DATABASE_CONNECT_ARGS = os.getenv('DATABASE_CONNECT_ARGS') or '{"timeout": 30}'

DEBUG = os.getenv("DEBUG", "0") == "1"

if not os.path.exists("data"):
    os.mkdir("data")

engine = create_engine(
    DATABASE_URL,
    connect_args=json.loads(DATABASE_CONNECT_ARGS),
    echo=DEBUG
)

md_obj = MetaData()



posts_table = Table(
    "posts",
    md_obj,
    Column("id", VARCHAR, primary_key=True),
    Column("text", VARCHAR),
    Column("has_cw", BOOLEAN),
    Column("visibility", VARCHAR),
    Column("author", VARCHAR)
)

last_scan_table = Table(
    "last_scan",
    md_obj,
    Column("id", VARCHAR, primary_key=True),
    Column("last_scan", DateTime, nullable=False)
)


md_obj.create_all(engine, checkfirst=True)
