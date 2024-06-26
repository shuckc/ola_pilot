from _typeshed import Incomplete
from typing import Optional

def get_api_from_environment(api=...): ...
def list_available_ports(
    ports: Incomplete | None = ..., midiio: Incomplete | None = ...
) -> None: ...
def list_input_ports(api=...) -> None: ...
def list_output_ports(api=...) -> None: ...
def open_midiport(
    port: Optional[str],
    type_: str = ...,
    api=...,
    use_virtual: bool = ...,
    interactive: bool = ...,
    client_name: Incomplete | None = ...,
    port_name: Incomplete | None = ...,
): ...
def open_midiinput(
    port: Optional[str],
    api=...,
    use_virtual: bool = ...,
    interactive: bool = ...,
    client_name: Incomplete | None = ...,
    port_name: Incomplete | None = ...,
): ...
def open_midioutput(
    port: Optional[str],
    api=...,
    use_virtual: bool = ...,
    interactive: bool = ...,
    client_name: Incomplete | None = ...,
    port_name: Incomplete | None = ...,
): ...
