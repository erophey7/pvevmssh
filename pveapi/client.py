import aiohttp
from urllib.parse import urljoin
from .exceptions import APIRequestError

class ProxmoxClient:
    def __init__(self, host, token_id, token_secret, verify_ssl=True):
        """
        Инициализация клиента с API токеном.
        :param host: адрес ноды Proxmox (например, 'https://192.168.1.100:8006')
        :param token_id: ID токена (например, 'root@pam!my-token')
        :param token_secret: секрет токена
        :param verify_ssl: проверять SSL-сертификат
        """
        self.base_url = host.rstrip('/')
        self.verify_ssl = verify_ssl
        self.token_id = token_id
        self.token_secret = token_secret
        self.session = None

    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        self.session.headers.update({
            'Authorization': f'PVEAPIToken={self.token_id}={self.token_secret}'
        })
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def _request(self, method, endpoint, params=None, data=None, json_data=None):
        url = urljoin(self.base_url, endpoint)
        async with self.session.request(
            method=method,
            url=url,
            params=params,
            data=data,
            json=json_data,
            ssl=self.verify_ssl
        ) as resp:
            if resp.status >= 400:
                try:
                    err_data = await resp.json()
                    error_msg = err_data.get('errors', err_data.get('message', str(resp.status)))
                except:
                    error_msg = await resp.text() or str(resp.status)
                raise APIRequestError(f"Request failed: {resp.status} - {error_msg}")
            result = await resp.json()
            return result.get('data', result)

    async def get(self, endpoint, params=None):
        return await self._request('GET', endpoint, params=params)

    async def post(self, endpoint, data=None, json_data=None):
        return await self._request('POST', endpoint, data=data, json_data=json_data)

    async def put(self, endpoint, data=None, json_data=None):
        return await self._request('PUT', endpoint, data=data, json_data=json_data)

    async def delete(self, endpoint):
        return await self._request('DELETE', endpoint)