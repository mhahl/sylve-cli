"""Local VNC bridge: expose a Sylve VM console as a loopback RFB socket."""

# shortcut: raw TCP bridge avoids adding a VNC or WebSocket dependency.
# Upgrade to a real websockify helper only if subprotocols or proxies are needed.

from __future__ import annotations

import shlex
import shutil
import socket
import struct
import subprocess
import sys
import threading
from typing import TYPE_CHECKING, Any

from sylve_cli.client import ResourceNotFoundError, SylveError
from sylve_cli.console_ws import (
    _OP_BINARY,
    _OP_CLOSE,
    _OP_CONTINUATION,
    _OP_PING,
    _OP_PONG,
    _OP_TEXT,
    _open_websocket,
    build_ws_auth_hex,
    decode_server_frame,
    encode_client_frame,
    resolve_console_hostname,
)
from sylve_cli.formatter import err_console

if TYPE_CHECKING:
    from sylve_cli.client import SylveClient


def parse_close_frame(payload: bytes) -> tuple[int, str]:
    """Decode a WebSocket close frame into its code and reason."""
    if len(payload) < 2:
        return 1005, ""
    code = struct.unpack("!H", payload[:2])[0]
    return code, payload[2:].decode("utf-8", errors="replace")


def close_message(code: int, reason: str, label: str, overtake: bool) -> SylveError:
    """Turn a WebSocket close code from the VNC relay into a clear error."""
    if code == 1013:
        hint = "Re-run with --overtake to take it over." if not overtake else ""
        return SylveError(f"Another client is already attached to {label}. {hint}".strip())
    if reason and "overtaken" in reason.lower():
        return SylveError(f"{label} was taken over by another client.")
    if code == 1011:
        return SylveError(
            f"{label} refused the VNC connection. Check that the VM is running "
            "and its VNC backend is healthy."
        )
    detail = f" ({reason})" if reason else ""
    return SylveError(f"{label} closed the VNC session with code {code}{detail}.")


def _viewer_command(address: str, port: int, override: str | None) -> list[str] | None:
    """Build the viewer command line for this platform, or None if none is installed."""
    if override:
        return [
            part.format(host=address, port=port, url=f"vnc://{address}:{port}")
            for part in shlex.split(override)
        ]
    if sys.platform == "darwin":
        return ["open", f"vnc://{address}:{port}"]
    # TigerVNC reads host:PORT as a display number, so an explicit port needs "::".
    candidates: list[list[str]] = [
        ["xtigervncviewer", f"{address}::{port}"],
        ["vncviewer", f"{address}::{port}"],
        ["remmina", "-c", f"vnc://{address}:{port}"],
        ["gvncviewer", f"{address}::{port}"],
        ["vinagre", f"{address}::{port}"],
    ]
    for candidate in candidates:
        if shutil.which(candidate[0]):
            return candidate
    return None


def _launch_viewer(command: list[str] | None, url: str) -> None:
    if command is None:
        err_console.print(
            f"[yellow]No VNC viewer found.[/yellow] Open [bold]{url}[/bold] manually, "
            "or pass --viewer CMD."
        )
        return
    try:
        subprocess.Popen(  # noqa: S603 - fixed argument list, user supplied command
            command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        err_console.print(
            f"[yellow]Could not start '{command[0]}': {exc}.[/yellow] "
            f"Open [bold]{url}[/bold] manually."
        )


def _bridge(ws: Any, ws_buffer: bytearray, viewer: Any, label: str, overtake: bool) -> None:
    """Relay binary frames between the WebSocket and the local viewer socket."""
    stop = threading.Event()
    closing = threading.Event()
    failure: list[SylveError] = []
    write_lock = threading.Lock()

    def server_to_viewer() -> None:
        try:
            while not stop.is_set():
                frame = decode_server_frame(ws, ws_buffer)
                if frame is None:
                    if closing.is_set():
                        return
                    raise SylveError(f"{label} closed the VNC session.")
                opcode, payload = frame
                if opcode == _OP_PING:
                    with write_lock:
                        ws.sendall(encode_client_frame(payload, _OP_PONG))
                elif opcode == _OP_CLOSE:
                    raise close_message(*parse_close_frame(payload), label, overtake)
                elif opcode in (_OP_TEXT, _OP_BINARY, _OP_CONTINUATION):
                    viewer.sendall(payload)
        except KeyboardInterrupt:
            pass
        except SylveError as exc:
            failure.append(exc)
        except OSError as exc:
            if not closing.is_set():
                failure.append(SylveError(f"VNC connection lost: {exc}."))
        finally:
            stop.set()
            try:
                viewer.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass

    reader = threading.Thread(target=server_to_viewer, daemon=True)
    reader.start()
    try:
        while not stop.is_set():
            data = viewer.recv(65536)
            if not data:
                break
            with write_lock:
                ws.sendall(encode_client_frame(data, _OP_BINARY))
    except OSError:
        pass
    except KeyboardInterrupt:
        pass
    finally:
        stop.set()
        closing.set()
        try:
            with write_lock:
                ws.sendall(encode_client_frame(struct.pack("!H", 1000), _OP_CLOSE))
        except OSError:
            pass
        reader.join(timeout=2)
    if failure:
        raise failure[0]


def serve_vnc(
    client: SylveClient,
    rid: int | str,
    *,
    node: str | None = None,
    overtake: bool = False,
    local_port: int = 0,
    viewer: str | None = None,
    print_only: bool = False,
    name: str | None = None,
) -> None:
    """Expose a VM's VNC console on loopback and open a local viewer."""
    label = f"VM {name or rid}"
    detail = client.get(f"/vm/{rid}", node=node)
    if not isinstance(detail, dict):
        raise SylveError(f"Unexpected response reading {label}.")
    if not detail.get("vncEnabled"):
        raise SylveError(
            f"VNC is disabled for {label}. Enable it with "
            f"""sylve vm hardware-vnc {rid} -d """
            """'{"vncEnabled":true,"vncResolution":"1024x768","vncWait":false}'."""
        )
    vnc_port = detail.get("vncPort")
    if not vnc_port:
        raise SylveError(f"{label} has no VNC port assigned. Re-apply its VNC configuration.")

    target_host = resolve_console_hostname(client, node)
    auth_hex = build_ws_auth_hex(client.context.token, target_host)
    params: dict[str, Any] = {"auth": auth_hex}
    if overtake:
        params["overtake"] = "true"

    try:
        ws, ws_buffer = _open_websocket(client, f"/vnc/{vnc_port}", params, target_host)
    except ResourceNotFoundError as exc:
        raise ResourceNotFoundError(
            f"No VM owns VNC port {vnc_port} on node {target_host}. "
            "Pass --node with the node that runs the VM."
        ) from exc

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            listener.bind(("127.0.0.1", local_port))
        except OSError as exc:
            raise SylveError(f"Cannot listen on 127.0.0.1:{local_port}: {exc}.") from exc
        listener.listen(1)
        bound_port = listener.getsockname()[1]
        url = f"vnc://127.0.0.1:{bound_port}"

        err_console.print(f"{label} VNC ready at {url}", style="green", markup=False)
        password = str(detail.get("vncPassword") or "").strip()
        if password:
            err_console.print(f"VNC password: {password}", style="dim", markup=False)
        err_console.print("Press Ctrl-C to stop the bridge.", style="dim")

        if not print_only:
            _launch_viewer(_viewer_command("127.0.0.1", bound_port, viewer), url)

        viewer_sock, _ = listener.accept()
        with viewer_sock:
            viewer_sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            _bridge(ws, ws_buffer, viewer_sock, label, overtake)
    finally:
        listener.close()
        ws.close()
