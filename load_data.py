import enum
import json
import aiomysql
import asyncio
import time
import datetime
try:
    import config
except ModuleNotFoundError:
    import config_default as config


with open("autosave.bak", "r") as f:
    data = json.load(f)
items = list(data["by_id"].values())

loop = asyncio.get_event_loop()


async def main():
    conn = await aiomysql.connect(
        host=config.MYSQL_HOST,
        user=config.MYSQL_USER,
        password=config.MYSQL_PASSWORD,
        db=config.MYSQL_DATABASE,
        port=config.MYSQL_PORT,
        loop=loop
    )
    async with conn.cursor() as cursor:
        for i, item in enumerate(items):
            time_tuple = time.strptime(item["time"], "%Y.%m.%d %H:%M")
            timestamp = time.mktime(time_tuple)
            formatted_time = datetime.datetime.fromtimestamp(timestamp)
            await cursor.execute("""
            INSERT INTO request (id,time,song_id,comment,requester,target,anonymous,password,checked)
            VALUES
            (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (
                item["submit_id"], formatted_time, item["song_id"], item["comment"], item[
                    "orderer"], item["orderto"], item["anonymous"], item["password"], item["checked"]
            ))
            print(f"{i+1}/{len(items)}")
    await conn.commit()
    conn.close()

loop.run_until_complete(main())
