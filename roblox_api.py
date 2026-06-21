import aiohttp
import logging

logger = logging.getLogger(__name__)

ROBLOX_USERS_API = "https://users.roblox.com/v1/usernames/users"
ROBLOX_THUMBNAILS_API = "https://thumbnails.roblox.com/v1/users/avatar-headshot"
ROBLOX_USER_API = "https://users.roblox.com/v1/users"


async def search_roblox_users(username: str) -> list:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                ROBLOX_USERS_API,
                json={"usernames": [username], "excludeBannedUsers": False},
                headers={"Content-Type": "application/json"}
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("data", [])
    except Exception as e:
        logger.error(f"Roblox search error: {e}")
    return []


async def get_user_avatar_url(user_id: int) -> str:
    try:
        async with aiohttp.ClientSession() as session:
            url = f"{ROBLOX_THUMBNAILS_API}?userIds={user_id}&size=420x420&format=Png&isCircular=false"
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    items = data.get("data", [])
                    if items:
                        return items[0].get("imageUrl", "")
    except Exception as e:
        logger.error(f"Roblox avatars error: {e}")
    return ""


async def get_user_by_id(user_id: int) -> dict:
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{ROBLOX_USER_API}/{user_id}") as resp:
                if resp.status == 200:
                    return await resp.json()
    except Exception as e:
        logger.error(f"Roblox user info error: {e}")
    return {}
