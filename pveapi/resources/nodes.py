from .base import ResourceManager

class NodesManager(ResourceManager):
    async def list(self):
        return await self.client.get('/nodes')

    async def get(self, node):
        return await self.client.get(f'/nodes/{node}')

    async def status(self, node):
        return await self.client.get(f'/nodes/{node}/status')