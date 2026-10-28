"""WebSocket console client for VM serial consoles, jail consoles, and host terminals."""

# shortcut: stdlib RFC 6455 client avoids adding a third-party WebSocket dependency.
# Upgrade to websockets if subprotocol negotiation or compression is needed later.

from __future__ import annotations

import base64
import hashlib
import json
import os
import selectors
import shutil
import signal
import socket
import ssl
import struct
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode, urlparse

from sylve_cli.client import (
    ResourceNotFoundError,
    SessionExpiredError,
    SylveAPIError,
    SylveError,
)
from sylve_cli.formatter import err_console

if TYPE_CHECKING:
    from sylve_cli.client import SylveClient

_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
_OP_CONTINUATION = 0x0
_OP_TEXT = 0x1
_OP_BINARY = 0x2
_OP_CLOSE = 0x8
_OP_PING = 0x9
_OP_PONG = 0xA

CTRL_INPUT = b"\x00"
CTRL_RESIZE = b"\x01"
CTRL_EXTRA = b"\x02"

_ERROR_HINTS: dict[str, str] = {
    "vm_serial_console_disabled": (
        "The VM serial console is disabled. Enable it with "
        "'sylve vm options-serial-console <rid> --data '{\"serial\":true}''."
    ),
    "vm_console_requires_running_vm": (
        "The VM is not running. Start it with 'sylve vm start <vm>' first."
    ),
    "vm_domain_not_defined": (
        "The VM domain is not defined on this node. Start the VM before attaching."
    ),
    "replication_lease_not_owned": (
        "This node does not own the replication lease for the guest. "
        "Pass --node with the active node."
    ),
    "selected_node_offline": "The selected cluster node is offline.",
    "selected_node_not_found": "The selected cluster node was not found.",
}


def build_ws_auth_hex(token: str, hostname: str) -> str:
    """Build the hex-encoded ``auth`` query parameter expected by Sylve WebSockets.

    Sylve's ``authenticateConsole`` middleware decodes the hex string as JSON
    ``{"hash": "<sha256(jwt)>", "hostname": "<node>"}`` and looks up the active
    session token by its SHA-256 digest while ``EnsureCorrectHost`` routes the
    upgrade to ``hostname``.
    """
    clean_token = token.strip()
    if not clean_token:
        raise SessionExpiredError(
            "No authentication token found. Log in with 'sylve login <server-url>' first."
        )
    clean_host = hostname.strip()
    if not clean_host:
        raise SylveError("Console attach requires a target node hostname. Pass --node <hostname>.")
    digest = hashlib.sha256(clean_token.encode("utf-8")).hexdigest()
    payload = json.dumps({"hash": digest, "hostname": clean_host}, separators=(",", ":"))
    return payload.encode("utf-8").hex()


def resolve_console_hostname(client: SylveClient, node: str | None = None) -> str:
    """Resolve the target node hostname required by WebSocket console endpoints."""
    resolved = client.resolve_node_hostname(node)
    if resolved:
        return resolved
    if client.context.hostname:
        return client.context.hostname
    try:
        info = client.get("/info/node")
        if isinstance(info, dict) and info.get("hostname"):
            return str(info["hostname"])
    except SylveError:
        pass
    parsed = urlparse(client.context.server)
    if parsed.hostname:
        return parsed.hostname
    raise SylveError("Could not determine target node hostname. Pass --node <hostname>.")


def format_console_http_error(status: int, body: bytes, path: str) -> SylveError:
    """Convert a rejected WebSocket HTTP upgrade response into a clear error."""
    code = ""
    detail = ""
    if body:
        try:
            parsed = json.loads(body.decode("utf-8", errors="replace"))
            if isinstance(parsed, dict):
                code = str(parsed.get("message") or parsed.get("error") or "")
                raw_err = parsed.get("error")
                if isinstance(raw_err, str) and raw_err != code:
                    detail = raw_err
        except ValueError:
            detail = body.decode("utf-8", errors="replace").strip()

    if status == 401:
        return SessionExpiredError(
            "Server rejected console authentication (HTTP 401). Re-authenticate with 'sylve login'."
        )
    if status == 404:
        return ResourceNotFoundError(f"Console target '{path}' was not found (HTTP 404).")
    if code in _ERROR_HINTS:
        return SylveAPIError(_ERROR_HINTS[code], status_code=status, error_code=code)
    if status == 403:
        msg = f"Console access denied on '{path}' (HTTP 403"
        msg += f": {code})." if code else "). Local administrator privileges are required."
        return SylveAPIError(msg, status_code=status, error_code=code)
    if status == 409:
        reason = detail or code or "guest console is not ready"
        return SylveAPIError(
            f"Console cannot attach in the guest's current state (HTTP 409: {reason}).",
            status_code=status,
            error_code=code,
        )
    if status == 503:
        reason = detail or code or "console service unavailable"
        return SylveAPIError(
            f"Console service is unavailable (HTTP 503: {reason}).",
            status_code=status,
            error_code=code,
        )
    summary = detail or code or f"HTTP {status}"
    return SylveAPIError(
        f"Console handshake failed on '{path}': {summary}.",
        status_code=status,
        error_code=code,
    )


def encode_client_frame(payload: bytes, opcode: int = _OP_BINARY) -> bytes:
    """Encode one masked client-to-server RFC 6455 frame."""
    mask_key = os.urandom(4)
    length = len(payload)
    header = bytearray([0x80 | (opcode & 0x0F)])
    if length < 126:
        header.append(0x80 | length)
    elif length < 65536:
        header.append(0x80 | 126)
        header.extend(struct.pack("!H", length))
    else:
        header.append(0x80 | 127)
        header.extend(struct.pack("!Q", length))
    header.extend(mask_key)
    masked = bytes(b ^ mask_key[i & 3] for i, b in enumerate(payload))
    return bytes(header) + masked


def decode_server_frame(sock: Any, buffer: bytearray) -> tuple[int, bytes] | None:
    """Read and decode one frame from *sock*, using *buffer* for leftover bytes."""

    def _ensure(n: int) -> bool:
        while len(buffer) < n:
            chunk = sock.recv(4096)
            if not chunk:
                return False
            buffer.extend(chunk)
        return True

    if not _ensure(2):
        return None
    b0, b1 = buffer[0], buffer[1]
    opcode = b0 & 0x0F
    masked = bool(b1 & 0x80)
    length = b1 & 0x7F
    offset = 2
    if length == 126:
        if not _ensure(4):
            return None
        length = struct.unpack("!H", buffer[2:4])[0]
        offset = 4
    elif length == 127:
        if not _ensure(10):
            return None
        length = struct.unpack("!Q", buffer[2:10])[0]
        offset = 10
    mask_bytes = b""
    if masked:
        if not _ensure(offset + 4):
            return None
        mask_bytes = bytes(buffer[offset : offset + 4])
        offset += 4
    if not _ensure(offset + length):
        return None
    payload = bytes(buffer[offset : offset + length])
    del buffer[: offset + length]
    if masked:
        payload = bytes(b ^ mask_bytes[i & 3] for i, b in enumerate(payload))
    return opcode, payload


def _open_websocket(
    client: SylveClient,
    path: str,
    params: dict[str, Any],
    hostname: str,
) -> tuple[Any, bytearray]:
    """Open a TCP/TLS connection and perform the RFC 6455 Upgrade handshake."""
    parsed = urlparse(client.context.server)
    scheme = (parsed.scheme or "https").lower()
    host = parsed.hostname or "localhost"
    port = parsed.port or (443 if scheme == "https" else 80)

    raw_sock: Any = socket.create_connection((host, port), timeout=client.timeout)
    if scheme == "https":
        if client.context.verify_ssl:
            ssl_ctx = ssl.create_default_context()
            if client.context.ca_cert:
                ssl_ctx.load_verify_locations(cafile=str(Path(client.context.ca_cert).expanduser()))
            sock: Any = ssl_ctx.wrap_socket(raw_sock, server_hostname=host)
        else:
            ssl_ctx = ssl._create_unverified_context()  # noqa: SLF001
            sock = ssl_ctx.wrap_socket(raw_sock, server_hostname=host)
    else:
        sock = raw_sock

    ws_key = base64.b64encode(os.urandom(16)).decode("ascii")
    query = urlencode({k: v for k, v in params.items() if v is not None})
    req_path = f"/api{path}" + (f"?{query}" if query else "")
    host_header = f"{host}:{port}" if parsed.port else host

    lines = [
        f"GET {req_path} HTTP/1.1",
        f"Host: {host_header}",
        "Upgrade: websocket",
        "Connection: Upgrade",
        f"Sec-WebSocket-Key: {ws_key}",
        "Sec-WebSocket-Version: 13",
        f"X-Current-Hostname: {hostname}",
        "",
        "",
    ]
    sock.sendall("\r\n".join(lines).encode("utf-8"))

    buf = bytearray()
    while b"\r\n\r\n" not in buf:
        chunk = sock.recv(4096)
        if not chunk:
            sock.close()
            raise SylveError(f"Connection closed during WebSocket handshake for '{path}'.")
        buf.extend(chunk)

    header_end = buf.index(b"\r\n\r\n")
    header_block = bytes(buf[:header_end]).decode("iso-8859-1", errors="replace")
    rest = bytearray(buf[header_end + 4 :])

    status_line = header_block.splitlines()[0] if header_block else ""
    parts = status_line.split(" ", 2)
    status_code = int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else 0

    headers: dict[str, str] = {}
    for line in header_block.splitlines()[1:]:
        if ":" in line:
            k, v = line.split(":", 1)
            headers[k.strip().lower()] = v.strip()

    if status_code != 101:
        content_len = int(headers.get("content-length") or 0)
        while content_len and len(rest) < content_len:
            try:
                more = sock.recv(4096)
            except OSError:
                break
            if not more:
                break
            rest.extend(more)
        sock.close()
        raise format_console_http_error(status_code, bytes(rest), path)

    expected_accept = base64.b64encode(
        hashlib.sha1((ws_key + _WS_GUID).encode("ascii")).digest()
    ).decode("ascii")
    if headers.get("sec-websocket-accept") != expected_accept:
        sock.close()
        raise SylveError("Server returned an invalid Sec-WebSocket-Accept header.")

    sock.settimeout(None)
    return sock, rest


def build_resize_frame(cols: int, rows: int) -> bytes:
    """Build a resize control frame (``0x01`` + JSON ``{"rows": R, "cols": C}``)."""
    body = json.dumps({"rows": max(1, rows), "cols": max(1, cols)}, separators=(",", ":")).encode(
        "utf-8"
    )
    return encode_client_frame(CTRL_RESIZE + body, _OP_BINARY)


def scan_detach_escape(data: bytes, at_line_start: bool) -> tuple[bytes, bool, bool, bytes]:
    """Filter SSH-style ``~.`` detach sequences after a newline or session start.

    Returns ``(forwarded_bytes, new_at_line_start, detach_requested, pending)``.
    ``~~`` after a newline forwards a single ``~``. A trailing lone ``~`` is held
    in ``pending`` and must be prepended to the next read: a raw terminal
    delivers each keystroke separately, so ``~`` and ``.`` rarely arrive together.
    """
    out = bytearray()
    i = 0
    n = len(data)
    while i < n:
        byte = data[i]
        if at_line_start and byte == ord("~"):
            if i + 1 == n:
                return bytes(out), True, False, b"~"
            nxt = data[i + 1]
            if nxt == ord("."):
                return bytes(out), False, True, b""
            if nxt == ord("~"):
                out.append(ord("~"))
                at_line_start = False
                i += 2
                continue
        out.append(byte)
        at_line_start = byte in (0x0A, 0x0D)
        i += 1
    return bytes(out), at_line_start, False, b""


def _send_terminal_size(sock: Any) -> None:
    size = shutil.get_terminal_size((80, 24))
    sock.sendall(build_resize_frame(size.columns, size.lines))


def attach_console(
    client: SylveClient,
    path: str,
    *,
    node: str | None = None,
    extra_params: dict[str, Any] | None = None,
    takeover: bool = True,
    kill_on_exit: bool = False,
    banner: str | None = None,
) -> None:
    """Attach the local terminal to a Sylve WebSocket console until ``~.`` or EOF."""
    client._ensure_valid_token()  # noqa: SLF001
    target_host = resolve_console_hostname(client, node)
    auth_hex = build_ws_auth_hex(client.context.token, target_host)

    params: dict[str, Any] = dict(extra_params or {})
    params["auth"] = auth_hex

    sock, buffer = _open_websocket(client, path, params, target_host)
    if banner:
        err_console.print(f"[dim]{banner} (press Enter, then type ~. to detach)[/dim]")

    _send_terminal_size(sock)
    if takeover:
        sock.sendall(encode_client_frame(CTRL_EXTRA, _OP_BINARY))

    stdin_fd = sys.stdin.fileno() if sys.stdin.isatty() else None
    old_tty: Any = None
    termios_mod: Any = None
    if stdin_fd is not None:
        try:
            import termios
            import tty

            termios_mod = termios
            old_tty = termios.tcgetattr(stdin_fd)
            tty.setraw(stdin_fd)
        except Exception:  # pragma: no cover - non-POSIX fallback
            old_tty = None

    prev_winch: Any = None
    if hasattr(signal, "SIGWINCH"):

        def _on_winch(_signum: int, _frame: Any) -> None:
            try:
                _send_terminal_size(sock)
            except OSError:
                pass

        try:
            prev_winch = signal.signal(signal.SIGWINCH, _on_winch)
        except ValueError:
            prev_winch = None

    sel = selectors.DefaultSelector()
    sel.register(sock, selectors.EVENT_READ)
    if stdin_fd is not None:
        sel.register(stdin_fd, selectors.EVENT_READ)

    at_line_start = True
    pending = b""
    try:
        while True:
            events = sel.select(timeout=1.0)
            for key, _ in events:
                if key.fileobj is sock:
                    while True:
                        frame = decode_server_frame(sock, buffer)
                        if frame is None:
                            return
                        opcode, payload = frame
                        if opcode == _OP_CLOSE:
                            return
                        if opcode == _OP_PING:
                            sock.sendall(encode_client_frame(payload, _OP_PONG))
                            continue
                        if opcode == _OP_TEXT:
                            text = payload.decode("utf-8", errors="replace")
                            try:
                                msg = json.loads(text)
                                if isinstance(msg, dict) and msg.get("type") == "control-state":
                                    if takeover and not msg.get("hasControl"):
                                        sock.sendall(encode_client_frame(CTRL_EXTRA, _OP_BINARY))
                                    continue
                            except ValueError:
                                pass
                            os.write(sys.stdout.fileno(), payload)
                        elif opcode in (_OP_BINARY, _OP_CONTINUATION):
                            os.write(sys.stdout.fileno(), payload)
                        if not buffer:
                            break
                elif stdin_fd is not None and key.fileobj == stdin_fd:
                    raw = os.read(stdin_fd, 1024)
                    if not raw:
                        return
                    forwarded, at_line_start, detach, pending = scan_detach_escape(
                        pending + raw, at_line_start
                    )
                    if forwarded:
                        sock.sendall(encode_client_frame(CTRL_INPUT + forwarded, _OP_BINARY))
                    if detach:
                        if kill_on_exit:
                            kill_body = json.dumps({"kill": ""}).encode("utf-8")
                            sock.sendall(encode_client_frame(CTRL_EXTRA + kill_body, _OP_BINARY))
                        return
    finally:
        sel.close()
        if prev_winch is not None and hasattr(signal, "SIGWINCH"):
            try:
                signal.signal(signal.SIGWINCH, prev_winch)
            except ValueError:
                pass
        if old_tty is not None and stdin_fd is not None and termios_mod is not None:
            try:
                termios_mod.tcsetattr(stdin_fd, termios_mod.TCSADRAIN, old_tty)
            except Exception:
                pass
        try:
            sock.sendall(encode_client_frame(b"", _OP_CLOSE))
        except OSError:
            pass
        sock.close()
