import aiohttp
import os

CRYPTO_BOT_TOKEN = os.environ.get("CRYPTO_BOT_TOKEN", "")
CRYPTO_BOT_API = "https://pay.crypt.bot/api"


async def create_invoice(amount_usdt: float, description: str = "GubaShop payment") -> dict:
    """Create a CryptoBot invoice and return invoice data."""
    headers = {"Crypto-Pay-API-Token": CRYPTO_BOT_TOKEN}
    payload = {
        "asset": "USDT",
        "amount": str(round(amount_usdt, 4)),
        "description": description,
        "expires_in": 3600,
    }
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{CRYPTO_BOT_API}/createInvoice",
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                data = await resp.json()
                if data.get("ok"):
                    return {"ok": True, "pay_url": data["result"]["pay_url"], "invoice_id": data["result"]["invoice_id"]}
                else:
                    return {"ok": False, "error": str(data)}
    except Exception as e:
        return {"ok": False, "error": str(e)}
