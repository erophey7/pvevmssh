import aiohttp
import logging

logger = logging.getLogger(__name__)

async def is_proxmox_token_valid(host, token_id, token_secret, verify_ssl=False, timeout=5):
    """
    Асинхронная проверка валидности API токена.
    Возвращает True, если токен действителен, иначе False.
    """
    url = f"{host.rstrip('/')}/api2/json/version"
    headers = {'Authorization': f'PVEAPIToken={token_id}={token_secret}'}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, ssl=verify_ssl, timeout=timeout) as resp:
                logger.debug(f"Token {token_id} check result: {resp.json}")
                return resp.status == 200
    except:
        return False