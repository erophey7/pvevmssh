from .base import ResourceManager

class VMsManager(ResourceManager):
    async def list(self, node=None):
        if node:
            return await self.client.get(f'/nodes/{node}/qemu')
        nodes = await self.client.get('/nodes')
        vms = []
        for n in nodes:
            node_name = n['node']
            vms.extend(await self.client.get(f'/nodes/{node_name}/qemu'))
        return vms

    async def get_config(self, node, vmid):
        return await self.client.get(f'/nodes/{node}/qemu/{vmid}/config')

    async def status(self, node, vmid):
        return await self.client.get(f'/nodes/{node}/qemu/{vmid}/status/current')