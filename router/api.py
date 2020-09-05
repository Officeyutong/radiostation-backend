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
import aiomysql
router = Blueprint("api", __name__)


async def fetch_many_song_data(songs: typing.List[int]) -> typing.List[typing.Dict[str, str]]:
    async with main.client.get(main.make_url("/song/detail"), params={"ids": ",".join((str(x) for x in songs))},) as resp:
        resp: aiohttp.client.ClientResponse
        if """msg":"参数错误!""" in await resp.text():
            return []
        songs_data = (await resp.json()).get("songs", [])
    async with main.client.get(main.make_url("/song/url"), params={"id": ",".join(str(x["id"]) for x in songs_data)}) as resp:
        audio_urls = [item["url"] for item in (await resp.json())["data"]]
        print((await resp.json())["data"])
    result = []
    # print(songs_data[0])
    for i in range(len(songs_data)):
        result.append({
            "name": songs_data[i]["name"],
            "picture_url": songs_data[i]["al"]["picUrl"],
            "audio_url": audio_urls[i] or f"https://music.163.com/song/media/outer/url?id={songs_data[i]['id']}.mp3",
            "author": "/".join((item["name"] for item in songs_data[i]["ar"])),
            "id": songs_data[i]["id"]
        })
    copied: typing.List[typing.Union[int,
                                     typing.Dict[str, str]]] = songs.copy()
    for item in result:
        index = copied.index(item["id"])
        copied[index] = item
    bad_ids = []
    for i, item in enumerate(copied):
        if type(item) == int:
            bad_ids.append(i)
    for item in bad_ids:
        copied[item] = {
            "name": "歌曲ID错误",
            "picture_url": "",
            "audio_url": "",
            "author": "",
            "id": copied[item]
        }
    return copied


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
            song_datas = await fetch_many_song_data([item[0] for item in result])
            for item, song_data in zip(result, song_datas):
                song_id, count, _ = item
                # song_data = await fetch_song_data(song_id)
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


@router.route("/query", methods=["POST", "GET"])
async def api_query():
    json = (await request.get_json())
    req_id, password = json["ID"], json["password"]
    async with main.pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute("""
                SELECT * FROM request WHERE id = %s and password = %s
            """, (
                req_id, password
            ))
            ret = await cursor.fetchall()
            if len(ret) == 0:
                return make_response(-1, message="ID或密码错误")
            ret = ret[0]
            return make_response(0, data={
                "songID": ret["song_id"],
                "comment": ret["comment"],
                "requester": ret["requester"],
                "target": ret["target"],
                "anonymous": bool(ret["anonymous"]),
                "time": str(ret["time"])
            })


@router.route("/update", methods=["POST", "GET"])
async def api_get():
    json = (await request.get_json())
    req_id, password = json["ID"], json["password"]
    async with main.pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
                SELECT COUNT(*) FROM request WHERE id = %s and password = %s
            """, (
                req_id, password
            ))
            if (await cursor.fetchone())[0] == 0:
                return make_response(-1, message="用户名或密码错误")
            await cursor.execute("""
                UPDATE request SET
                song_id = %s,
                comment = %s,
                requester = %s,
                target = %s,
                anonymous = %s
                WHERE
                id = %s AND password = %s
            """, (
                json["song"], json["comment"], json["requester"], json["target"], json["anonymous"],
                req_id, password
            ))
            await conn.commit()
            return make_response(0, message="操作完成")


@router.route("/setcheck", methods=["POST"])
async def api_toggle_check():
    json = await request.get_json()
    password, request_id, checked = json["password"], json["ID"], json["checked"]
    if password != main.config.DJ_PASSWORD and password != main.config.ADMIN_PASSWORD:
        return make_response(-1, message="密码错误")
    async with main.pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
            UPDATE request SET checked = %s WHERE id = %s
            """, (
                checked, request_id
            ))
        await conn.commit()
    return make_response(0, message="ok")


@router.route("/manage", methods=["POST", "GET"])
async def api_manage():
    password = (await request.get_json())["password"]
    page = int((await request.get_json()).get("page", 1))
    if password == main.config.ADMIN_PASSWORD:
        is_admin = True
    elif password == main.config.DJ_PASSWORD:
        is_admin = False
    else:
        return make_response(-1, message="密码错误")
    result = []
    async with main.pool.acquire() as conn:
        async with conn.cursor(aiomysql.DictCursor) as cursor:
            await cursor.execute("""SELECT COUNT(DISTINCT song_id) as count FROM request""")
            item_count = (await cursor.fetchone())["count"]
            print(f"{item_count=}")
            page_count = int(
                math.ceil(item_count/main.config.BACKEND_REQUESTS_PER_PAGE))
            print(f"{page_count=}")
            await cursor.execute(f"""
                SELECT 
                song_id,
                COUNT(*) AS request_count,
                MIN(time) as earliest_time
                FROM request
                GROUP BY song_id
                ORDER BY request_count DESC,earliest_time ASC
                LIMIT {main.config.BACKEND_REQUESTS_PER_PAGE}
                OFFSET {(page-1)*main.config.BACKEND_REQUESTS_PER_PAGE}
            """)
            songs = [item["song_id"] for item in (await cursor.fetchall())]

            print(songs)
            songs_data = await fetch_many_song_data(songs)
            for song, song_data in zip(songs, songs_data):
                # song_data = await fetch_song_data(song)

                song_obj = {
                    "songData": {
                        "name": song_data["name"],
                        "picURL": song_data["picture_url"],
                        "audioURL": song_data["audio_url"],
                        "author": song_data["author"],
                        "songID": song
                    },
                    "requests": []

                }
                result.append(song_obj)
                reqs = song_obj["requests"]
                await cursor.execute(f"""
                SELECT
                time,
                id,
                comment,
                requester,
                target,
                anonymous,
                password,
                checked
                FROM request
                WHERE song_id = {song}
                ORDER BY time ASC
                """)
                items = (await cursor.fetchall())
                for req in items:
                    current_req = {
                        "ID": req["id"],
                        "checked": bool(req["checked"]),
                        "target": req["target"],
                        "time": str(req["time"]),
                        "comment": req["comment"],
                        "requester": req["requester"],
                        "anonymous": bool(req["anonymous"])
                    }
                    if is_admin:
                        current_req["password"] = req["password"]
                    else:
                        if req["anonymous"]:
                            current_req["requester"] = "匿名"
                    reqs.append(current_req)
    return make_response(0, isAdmin=is_admin, pageCount=page_count, data=result)


@router.route("/remove/request", methods=["POST", "GET"])
async def api_remove_request():
    json = await request.get_json()
    password, request_id = json["password"], json["ID"]
    if password != main.config.ADMIN_PASSWORD:
        return make_response(-1, message="密码错误")
    async with main.pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
            DELETE FROM request WHERE id = %s
            """, (request_id,))
        await conn.commit()
    return make_response(0, message="操作完成")


@router.route("/remove/song", methods=["POST", "GET"])
async def api_remove_song():
    json = await request.get_json()
    password, song_id = json["password"], json["ID"]
    if password != main.config.ADMIN_PASSWORD:
        return make_response(-1, message="密码错误")
    async with main.pool.acquire() as conn:
        async with conn.cursor() as cursor:
            await cursor.execute("""
            DELETE FROM request WHERE song_id = %s
            """, (song_id,))
        await conn.commit()
    return make_response(0, message="操作完成")


@router.route("/search", methods=["POST"])
async def api_search():
    keyword = (await request.get_json())["keyword"]
    if not keyword.strip():
        return make_response(-1, message="请输入关键字")
    async with main.client.get(main.make_url("/search"), params={"keywords": keyword, "limit": main.config.SEARCH_RESULT_COUNT_LIMIT}) as resp:
        # print((await resp.json()))
        json = await resp.json()
        if json["result"]["songCount"] == 0:
            return make_response(0, data=[])
        json_resp = json["result"]["songs"]
        print(json_resp)
        result = [
            {
                "name": item["name"],
                "songID":int(item["id"]),
                "author":"/".join((artist["name"] for artist in item["artists"]))
            }
            for item in json_resp
        ]
    return make_response(0, data=result)
