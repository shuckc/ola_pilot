# Generated by the protocol buffer compiler.  DO NOT EDIT!
# sources: rpc/Rpc.proto
# plugin: python-betterproto
from dataclasses import dataclass

import betterproto


class Type(betterproto.Enum):
    REQUEST = 1
    RESPONSE = 2
    RESPONSE_CANCEL = 3
    RESPONSE_FAILED = 4
    RESPONSE_NOT_IMPLEMENTED = 5
    DISCONNECT = 6
    DESCRIPTOR_REQUEST = 7
    DESCRIPTOR_RESPONSE = 8
    REQUEST_CANCEL = 9
    STREAM_REQUEST = 10


@dataclass
class RpcMessage(betterproto.Message):
    type: "Type" = betterproto.enum_field(1)
    id: int = betterproto.uint32_field(2)
    name: str = betterproto.string_field(3)
    buffer: bytes = betterproto.bytes_field(4)
