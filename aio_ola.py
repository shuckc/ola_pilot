import asyncio
import itertools
import struct
from typing import Optional

import betterproto  # for type hints

from ola.proto import (
    Ack,
    DmxData,
    OptionalUniverseRequest,
    PluginListReply,
    PluginListRequest,
    UniverseInfoReply,
    UniverseRequest,
)

# generated by protoc using betterproto
from ola.rpc import RpcMessage, Type
from desk import ControllerUniverseOutput


class OlaClient(ControllerUniverseOutput):
    def __init__(self, host="localhost", port=9010) -> None:
        self._handlers: dict[int, tuple[type[betterproto.Message], asyncio.Future]] = {}
        self._request_counter = itertools.count()
        self._host = host
        self._port = port
        self._writer: Optional[asyncio.StreamWriter] = None

    async def connect(self):
        self._reader, self._writer = await asyncio.open_connection(
            self._host, self._port
        )
        asyncio.create_task(self._handle_messages())

    async def _send_request(
        self,
        request: betterproto.Message,
        method_name: str,
        return_msg_class: type[betterproto.Message],
    ):
        req_id = next(self._request_counter)
        fut = asyncio.get_running_loop().create_future()

        rpc_message = RpcMessage()
        rpc_message.type = Type.REQUEST
        rpc_message.id = req_id
        rpc_message.name = method_name
        rpc_message.buffer = bytes(request)

        # stash expected return info and future for _handle_messages
        self._handlers[req_id] = (return_msg_class, fut)

        # prepare the 4-byte sz header and send
        rpc_bytes = bytes(rpc_message)
        h = (1 << 28) | len(rpc_bytes)
        header = struct.pack("<L", h)
        # print(f'sending {len(rpc_bytes)} bytes')
        payload = header + rpc_bytes
        # print(payload)
        if not self._writer:
            raise IOError("Stream not connected")
        self._writer.write(payload)

        return await fut

    async def _handle_messages(self):
        while True:
            header = await self._reader.readexactly(4)
            header_value = struct.unpack("<L", header)[0]
            # version = (header_value & 0xF0000000) >> 28
            sz = header_value & 0x0FFFFFF
            # print(f'Awaiting version {version} size {sz}')

            data = await self._reader.readexactly(sz)
            m = RpcMessage().parse(data)
            # print(m)
            # print(f'checking for handler for request {m.id}')
            mtype, fut = self._handlers[m.id]
            if m.type != Type.RESPONSE:
                t = Type(m.type)
                print(f"Unexpected message: {t.name}!")
                fut.set_exception(Exception(f"Unexpected reply {t.name}"))
            else:
                data = mtype().parse(m.buffer)
                # print(data)
                fut.set_result(data)

    async def get_plugin_list(self):
        request = PluginListRequest()
        return await self._send_request(request, "GetPlugins", PluginListReply)

    async def get_universes(self):
        request = OptionalUniverseRequest()
        return await self._send_request(request, "GetUniverseInfo", UniverseInfoReply)

    async def get_dmx(self, universe=0):
        request = UniverseRequest()
        request.universe = universe
        return await self._send_request(request, "GetDmx", DmxData)

    async def set_dmx(
        self, universe: int = 0, data: bytes = b"\0\0", priority: int = 0
    ):
        if not self._writer:
            return
        request = DmxData()
        request.universe = universe
        request.data = data
        request.priority = priority
        return await self._send_request(request, "UpdateDmxData", Ack)


async def main():
    client = OlaClient()
    await client.connect()
    print(await client.get_plugin_list())
    print(await client.get_universes())
    print(await client.get_dmx(universe=1))
    print(await client.set_dmx(universe=1, data=b"\0\0\0\0"))


if __name__ == "__main__":
    asyncio.run(main())
