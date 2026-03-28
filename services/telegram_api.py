import aiohttp

async def validate_token(token):
    url = f"https://api.telegram.org/bot{token}/getMe"
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                if data.get("ok"):
                    return {
                        "id": data["result"]["id"],
                        "username": data["result"]["username"],
                        "first_name": data["result"]["first_name"]
                    }
                return None
    except Exception:
        return None
