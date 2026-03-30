from .base import ResourceManager

class ContainersManager(ResourceManager):
    async def list(self, node=None):
        if node:
            return await self.client.get(f'/nodes/{node}/lxc')
        nodes = await self.client.get('/nodes')
        containers = []
        for n in nodes:
            node_name = n['node']
            containers.extend(await self.client.get(f'/nodes/{node_name}/lxc'))
        return containers

    async def get_config(self, node, vmid):
        return await self.client.get(f'/nodes/{node}/lxc/{vmid}/config')

    async def status(self, node, vmid):
        return await self.client.get(f'/nodes/{node}/lxc/{vmid}/status/current')