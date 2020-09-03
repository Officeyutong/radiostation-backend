import json
from typing import final
import aiohttp
from quart import Blueprint, request
from quart_cors import cors
from common.utils import unpack_argument, make_response
# from models import Request
import main
import time
import random
import datetime
import typing
import traceback
import math
router = Blueprint("api", __name__)


async def fetch_song_data(song_id: int) -> typing.Dict[str, str]:
    async with main.client.get(main.make_url("/song/detail"), params={"ids": song_id},) as resp:
        resp: aiohttp.client.ClientResponse
        json_resp = (await resp.json())["songs"]
        if len(json_resp) == 0:
            return {}
        song_data = json_resp[0]
        pic_url = None
        audio_url = None
        # 通过专辑信息来获取歌曲图片
        async with main.client.get(main.make_url("/album"), params={"id": song_data["al"]["id"]}) as resp:
            album_json_data = (await resp.json())["album"]
            pic_url = album_json_data["blurPicUrl"]
        # 获取歌曲链接
        try:
            async with main.client.get(main.make_url("/song/url"), params={"id": song_id}) as resp:
                audio_url = (await resp.json())["data"][0]["url"]
        except Exception:
            traceback.print_exc()
        return {
            "name": song_data["name"],
            "picture_url": pic_url,
            "audio_url": audio_url,
            "author": "/".join((item["name"] for item in song_data["ar"])),
            # "raw_data": song_data,
            # "album_data": album_json_data
        }


@router.route("/query_song", methods=["POST", "GET"])
async def api_query_song():
    song_id = (await request.get_json())["songID"]
    # print(f"querying {song_id}")
    result = await fetch_song_data(song_id)
    if len(result) == 0:
        return make_response(-1, message="歌曲ID错误")
    return make_response(0, data=result)


@router.route("/submit", methods=["POST", "GET"])
async def api_submit():
    user_json = (await request.get_json())
    song_id = user_json["songID"]
    requester = user_json["requester"]
    anonymous = user_json["anonymous"]
    target = user_json["target"]
    comment = user_json["comment"]
    password = "".join(str(random.randint(0, 9)) for i in range(6))
    # req = Request
    async with main.pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
            INSERT INTO request (
                time,song_id,comment,requester,target,anonymous,password
            )
            VALUES(
                %s,%s,%s,%s,%s,%s,%s
            )
            """, [
                datetime.datetime.now(),
                song_id,
                comment,
                requester,
                target,
                anonymous,
                password
            ])
            await conn.commit()
            last_id = cursor.lastrowid

    return make_response(0, message=f"您的歌曲已经提交成功，您的请求ID为 {last_id}，请求密码为: {password}，请牢记")


@router.route("/songlist", methods=["POST", "GET"])
async def api_songlist():
    json_data = await request.get_json()
    page = int(json_data.get("page", 1))
    final_result = []
    async with main.pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
            SELECT COUNT(DISTINCT song_id) FROM request
            """)
            item_count = (await cursor.fetchone())[0]
            page_count = int(
                math.ceil(item_count/main.config.REQUESTS_PER_PAGE))

            await cursor.execute(f"""
                SELECT 
                song_id,
                COUNT(*) as request_count,
                MAX(time) as newest 
                FROM request 
                GROUP BY song_id 
                ORDER BY request_count DESC, newest DESC
                LIMIT {main.config.REQUESTS_PER_PAGE}
                OFFSET {(page-1)*main.config.REQUESTS_PER_PAGE} 
            """)
            result = await cursor.fetchall()
            for item in result:
                song_id, count, _ = item
                song_data = await fetch_song_data(song_id)
                print(f"{song_id} fetched = {song_data}")
                if len(song_data) != 0:
                    current = {
                        "songData": {
                            "name": song_data["name"],
                            "songID": song_id,
                            "audioURL": song_data["audio_url"],
                            "author": song_data["author"],
                            "picURL": song_data["picture_url"]
                        },
                        "count": count
                    }
                else:
                    current = {
                        "songData": {
                            "name": "歌曲不存在",
                            "songID": song_id,
                            "audioURL": "",
                            "author": "",
                            "picURL": ""
                        },
                        "count": count
                    }
                final_result.append(current)
    return make_response(0, data=final_result, pageCount=page_count)
