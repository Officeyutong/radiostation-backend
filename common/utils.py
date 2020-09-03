import quart
from functools import wraps
import json


def unpack_argument(func):
    @wraps(func)
    async def wrapper():
        data = await quart.request.get_json() or {}
        return func(**data)
    return wrapper


def make_response(code, **kwargs):
    return json.dumps({
        "code": code,
        **kwargs
    })
