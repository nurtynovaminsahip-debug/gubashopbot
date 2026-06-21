import aiohttp


async def get_rates():
    """Get USDT and TON rates in RUB."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": "tether,the-open-network", "vs_currencies": "rub"},
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                data = await resp.json()
                usdt_rub = data.get("tether", {}).get("rub", 0)
                ton_rub = data.get("the-open-network", {}).get("rub", 0)
                return usdt_rub, ton_rub
    except Exception:
        return 0, 0


async def rub_to_usdt(rub_amount: float) -> float:
    """Convert RUB to USDT."""
    usdt_rub, _ = await get_rates()
    if usdt_rub and usdt_rub > 0:
        return rub_amount / usdt_rub
    return 0.0


async def get_crypto_bot_commission_amount(rub_amount: float) -> float:
    """Return USDT amount including CryptoBot ~1.5% commission."""
    usdt_amount = await rub_to_usdt(rub_amount)
    return round(usdt_amount * 1.015, 4)
