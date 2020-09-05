from quart import Quart
# from aiomysql.sa import create_engine
import aiomysql
import aiohttp
import asyncio
from quart_cors import cors
try:
    import config
except ModuleNotFoundError:
    import config_default as config

from urllib.parse import urljoin
from models import Request
def make_url(url): return urljoin(config.NETEASE_BACKEND, url)


app = Quart(__name__)

app = cors(app, allow_origin=["*"])


logger = app.logger


@app.before_serving
async def init():
    global pool, client
    client = aiohttp.ClientSession()
    print(f"Creating mysql engine...")
    pool = await aiomysql.create_pool(
        user=config.MYSQL_USER,
        password=config.MYSQL_PASSWORD,
        port=config.MYSQL_PORT,
        db=config.MYSQL_DATABASE,
        host=config.MYSQL_HOST,
        loop=asyncio.get_event_loop(),
        autocommit=True,
        minsize=1,
        maxsize=1
    )
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
                CREATE TABLE IF NOT EXISTS request (
                    id INTEGER PRIMARY KEY AUTO_INCREMENT,
                    time DATETIME NOT NULL,
                    song_id INTEGER NOT NULL,
                    comment LONGTEXT,
                    requester TEXT NOT NULL,
                    target TEXT,
                    anonymous BOOLEAN NOT NULL,
                    password VARCHAR(128) NOT NULL,
                    checked BOOLEAN NOT NULL DEFAULT FALSE,
                    INDEX(password),
                    INDEX(song_id),
                    INDEX(time)
                )
            """)
    print(f"Logging into netease...")
    async with client.post(make_url("/login/cellphone"), data={
        "phone": config.NETEASE_PHONE,
        "password": config.NETEASE_PASSWORD
    }) as resp:
        resp: aiohttp.client.ClientResponse
        print(await resp.text())


@app.after_serving
async def after_serving():
    global pool
    pool.close()
    await pool.wait_closed()
    await client.close()


def _load_routes():
    from router.api import router as router_api
    app.register_blueprint(router_api, url_prefix="/api/")


_load_routes()
