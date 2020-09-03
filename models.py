
from datetime import date
from sqlalchemy import Table, Column, MetaData, Integer, String, DateTime, Boolean
from sqlalchemy.dialects import mysql
import datetime
Request = Table(
    "request",
    MetaData(),
    Column("id", mysql.INTEGER, primary_key=True),
    Column("time", mysql.DATETIME, default=datetime.datetime.now),
    Column("song_id", mysql.INTEGER, index=True, nullable=False),
    Column("comment", mysql.LONGTEXT, nullable=True),
    Column("requester", mysql.TEXT, nullable=False),
    Column("target", mysql.TEXT, nullable=True),
    Column("anonymous", mysql.BOOLEAN, nullable=False),
    Column("password", mysql.VARCHAR(128), nullable=False, index=True)
)
