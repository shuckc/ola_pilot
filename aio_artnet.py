import asyncio
import socket
import struct
import ipaddress
import fcntl
from typing import Optional
import re

from desk import ControllerUniverseOutput, NetNode, Controller


class ArtNetNode(NetNode):
    def __init__(self, **kwargs) -> None:

        super().__init__(**kwargs)

    pass


ARTNET_PORT = 6454
ARTNET_PREFIX = bytes("Art-Net".encode() + b"\000")


# socket-io fnctl flags
# https://elixir.bootlin.com/linux/v4.2/source/include/uapi/linux/sockios.h#L43
SIOCGIFADDR = 0x8915
SIOCGIFNETMASK = 0x891B
SIOCGIFBRDADDR = 0x8919
SIOCGIFFLAGS = 0x8913

# interfaces *with an ip* are preferred in this order
PREFERED_INTERFACES_ORDER = ["enp.*", "wlp.*"]


def swap32(x):
    return int.from_bytes(
        x.to_bytes(4, byteorder="little"), byteorder="big", signed=False
    )


class ArtNetClientProtocol(asyncio.DatagramProtocol):
    def __init__(self, broadcast_ip: str, client: "ArtNetClient"):
        self.client = client
        self.transport = None
        self.handlers = {0x2000: self.on_art_poll, 0x2100: self.on_art_poll_reply}
        self.nodes: dict[int, ArtNetNode] = {}
        self.broadcast_ip = broadcast_ip

    def connection_made(self, transport):
        self.transport = transport

        sock = transport.get_extra_info("socket")
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        print("made:", self.transport)

    def datagram_received(self, data, addr):
        if data[0:8] == ARTNET_PREFIX:
            (opcode,) = struct.unpack("H", data[8:10])
            print(f"Received Art-net: op {opcode} from {addr}: {data[10:]}")
            h = self.handlers.get(opcode, None)
            if h:
                h(addr, data[10:])
        else:
            print(f"Received non Art-Net data {data} from {addr}")

    def on_art_poll(self, addr, data):
        ver, flags, priority = struct.unpack("HBB", data)
        print(f"Received Art-Net Poll: ver {ver} flags {flags} prio: {priority}")
        self.send_art_poll_reply(addr)

    def on_art_poll_reply(self, addr, data):
        (
            ip,
            port,
            fw,
            netsw,
            subsq,
            oemCode,
            ubeaVer,
            status,
            esta,
            portName,
            longName,
            report,
            numports,
        ) = struct.unpack("<IHHBBHBBH18s64s64sH", data[0:164])
        (
            ptype,
            ins,
            outs,
            swin,
            swout,
            acnprio,
            swmacro,
            swremote,
            style,
            mac,
            bindip,
            bindindex,
        ) = struct.unpack("4s4s4s4s4sBBB3xB6sIB", data[164:205])
        status2, goodout, status3, rdm, user, refresh, zfilter = struct.unpack(
            "B4sB6sHH8s", data[205:]
        )

        portName = portName.rstrip(b"\000").decode()
        longName = longName.rstrip(b"\000").decode()
        print(
            f"Received Art-Net PollReply: ip {ip} fw {fw} portName {portName} longName: {longName} port flags {ptype}"
        )

        ipa = ipaddress.IPv4Address(swap32(ip))

        nn = self.nodes.get(ip, None)
        if nn is None:
            print("protocol adding node")
            nn = ArtNetNode(address=f"{ipa}:{port}", name=longName)
            self.nodes[ip] = nn
            self.client.add_node(nn)

    async def send_art_poll(self):
        message = ARTNET_PREFIX + struct.pack("<HBBBB", 0x2000, 0, 14, 6, 16)
        while True:
            await asyncio.sleep(3)
            print(f"sending poll to {self.broadcast_ip}")
            self.transport.sendto(message, addr=(self.broadcast_ip, ARTNET_PORT))

    def send_art_poll_reply(self, addr):
        # message = ARTNET_PREFIX + struct.pack('<HBBBB', 0x2000, 0, 14, 6, 16)
        print(f"sending poll reply to {addr}")
        # self.transport.sendto(message, addr=(self.broadcast_ip, ARTNET_PORT))

    def error_received(self, exc):
        print("Error received:", exc)

    def connection_lost(self, exc):
        print("Connection closed")


class ArtNetClient(ControllerUniverseOutput):
    def __init__(self, host="localhost", port=9010, interface=None) -> None:

        # self._request_counter = itertools.count()
        self._host = host
        self._port = port
        self._writer: Optional[asyncio.StreamWriter] = None
        self.nodes: list[NetNode] = []
        self.controller: Optional[Controller] = None

        if interface is None:
            interface = get_preferred_artnet_interface()

        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            iface_bin = struct.pack("256s", bytes(interface, "utf-8"))
            packet_ip = fcntl.ioctl(s.fileno(), SIOCGIFADDR, iface_bin)[20:24]
            bcast = fcntl.ioctl(s.fileno(), SIOCGIFBRDADDR, iface_bin)[20:24]
            self.broadcast = socket.inet_ntoa(bcast)
            print(
                f"using interface {interface} with ip {socket.inet_ntoa(packet_ip)} broadcast ip {self.broadcast}"
            )

    async def connect(self, controller: Controller) -> asyncio.Future:
        print("connect")
        loop = asyncio.get_running_loop()

        on_con_lost = loop.create_future()

        # remote_addr=('192.168.1.255', ARTNET_PORT),
        transport, protocol = await loop.create_datagram_endpoint(
            lambda: ArtNetClientProtocol(self.broadcast, self),
            local_addr=("0.0.0.0", ARTNET_PORT),
            family=socket.AF_INET,
            allow_broadcast=True,
        )

        asyncio.create_task(protocol.send_art_poll())

        self.transport = transport
        self.protocol = protocol
        self.controller = controller

        return on_con_lost

    async def set_dmx(
        self, universe: int = 0, data: bytes = b"\0\0", priority: int = 0
    ):
        pass

    def get_nodes(self) -> list[NetNode]:
        return self.nodes

    def add_node(self, node: ArtNetNode):
        print("client adding node")
        self.nodes.append(node)
        if self.controller:
            self.controller.add_node(node)


def get_iface_ip(iface: str):
    """
    Get network interface IP using the network interface name
    :param iface: Interface name (like eth0, enp2s0, etc.)
    :return IP address in the form XX.XX.XX.XX
    """
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            iface_bin = struct.pack("256s", bytes(iface, "utf-8"))
            packet_ip = fcntl.ioctl(s, SIOCGIFADDR, iface_bin)[20:24]
            netmask = fcntl.ioctl(s, SIOCGIFNETMASK, iface_bin)[20:24]
            bcast = fcntl.ioctl(s, SIOCGIFBRDADDR, iface_bin)[20:24]
        return map(socket.inet_ntoa, [packet_ip, netmask, bcast])
    except OSError:
        return None, None, None
    # socket.inet_ntoa(fcntl.ioctl(s, 35099, struct.pack('256s', iface))[20:24])


def get_preferred_artnet_interface() -> str:
    preferred = []
    matchers = list(map(re.compile, PREFERED_INTERFACES_ORDER))
    print(matchers)
    for idx, name in socket.if_nameindex():

        packet, netmask, bcast = get_iface_ip(name)
        print(f"idx={idx} name={name} {packet} {netmask} {bcast}")
        # looks like an explicit class-A primary interface for Art-Net
        if packet is None:
            # no ip address, skip
            pass
        elif netmask == "255.0.0.0" and packet.startswith("2."):
            preferred.append((-1, name))
        else:
            for i, p in enumerate(matchers):
                if re.match(p, name):
                    print(f"found interface prefix {p} priority {i}")
                    preferred.append((i, name))
                    break
            else:
                preferred.append((10, name))

    preferred = sorted(preferred)
    print(f"preferred interfaces: {preferred}")
    interface = preferred[0][1]
    return interface


async def main():
    client = ArtNetClient()
    on_con_lost = await client.connect(None)
    # print(await client.get_dmx(universe=1))
    # print(await client.set_dmx(universe=1, data=b"\0\0\0\0"))

    try:
        await on_con_lost
    finally:
        pass


if __name__ == "__main__":
    asyncio.run(main())