"""Sylve API HTTP client with cluster-wide routing and guest-to-node resolution."""

from __future__ import annotations

import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import httpx

from sylve_cli.config import ContextConfig, extract_token_expiry, normalize_server_url


class SylveError(Exception):
    """Base exception for Sylve CLI errors."""


class SessionExpiredError(SylveError):
    """Raised when the stored JWT token is missing, expired, or rejected with 401."""


class SylveAPIError(SylveError):
    """Raised when the Sylve API returns an error status or non-2xx HTTP code."""

    def __init__(
        self,
        message: str,
        status_code: int = 0,
        error_code: str = "",
        data: Any = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.data = data


class ResourceNotFoundError(SylveError):
    """Raised when a VM, Jail, Node, or other resource cannot be found."""


_HTML_BODY_RE = re.compile(r"<[a-zA-Z!/][^>]*>")
_MAX_ERROR_BODY = 200


def _response_error_message(status_code: int, payload: Any, what: str) -> str:
    """Build a one-line error from a failed response.

    The Sylve web UI serves an HTML shell on some unreleased routes, and raw
    HTML must never be printed as if it were an error message. JSON envelopes
    supply ``message``/``error``; anything else is reduced to a short snippet.
    """
    if isinstance(payload, dict):
        code = str(payload.get("error") or "")
        message = str(payload.get("message") or code or "").strip()
        if code and code != message:
            message = f"{message} ({code})"
        if message:
            return f"HTTP {status_code} {what}: {message}"
    text = payload.strip() if isinstance(payload, str) else ""
    if text and not _HTML_BODY_RE.search(text):
        snippet = text[:_MAX_ERROR_BODY].replace("\n", " ")
        return f"HTTP {status_code} {what}: {snippet}"
    if text:
        return (
            f"HTTP {status_code} {what}: server returned an HTML page (endpoint not implemented?)"
        )
    return f"HTTP {status_code} {what}"


class SylveClient:
    """HTTP client for the Sylve API with multi-node cluster support."""

    def __init__(
        self,
        context: ContextConfig,
        node_override: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.context = context
        self.node_override = node_override
        self.timeout = timeout
        self._base_url = f"{normalize_server_url(context.server)}/api"

        verify: bool | str = context.verify_ssl
        if context.verify_ssl and context.ca_cert:
            verify = str(Path(context.ca_cert).expanduser())

        self._http = httpx.Client(
            base_url=self._base_url,
            verify=verify,
            timeout=timeout,
            follow_redirects=True,
        )
        self._nodes_cache: list[dict[str, Any]] | None = None
        self._resources_cache: list[dict[str, Any]] | None = None

    def close(self) -> None:
        """Close the underlying HTTPX client.

        Returns:
            None.

        Example:
            >>> client.close()
        """
        self._http.close()

    def __enter__(self) -> SylveClient:  # noqa: PYI034
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _ensure_valid_token(self) -> None:
        if not self.context.token:
            raise SessionExpiredError(
                "No authentication token found. Please log in with 'sylve login <server-url>'."
            )
        if self.context.is_token_expired():
            exp_dt = self.context.get_expiry_datetime()
            exp_str = exp_dt.strftime("%Y-%m-%d %H:%M:%S UTC") if exp_dt else "unknown time"
            raise SessionExpiredError(
                f"Authentication token expired at {exp_str}. "
                "Please re-authenticate with 'sylve login'."
            )

    def resolve_node_hostname(self, node_identifier: str | None) -> str | None:
        """Resolve a node identifier to a canonical hostname.

        Args:
            node_identifier: Hostname, UUID, or None for the default node.

        Returns:
            str | None: Canonical hostname, or None for cluster-wide requests.

        Example:
            >>> client.resolve_node_hostname("node1.lan")
            'node1.lan'
        """
        target = node_identifier or self.node_override or self.context.default_node
        if not target:
            return None
        target = target.strip()
        if not target or target.lower() == "all":
            return None

        # Check cached or live cluster nodes to allow matching by nodeUUID, ID, or hostname
        try:
            nodes = self.get_cluster_nodes()
        except SylveError:
            return target

        for n in nodes:
            hostname = str(n.get("hostname") or "")
            uuid = str(n.get("nodeUUID") or n.get("nodeUuid") or n.get("id") or "")
            if target.lower() in (hostname.lower(), uuid.lower()):
                return hostname or target
        return target

    def resolve_node_uuid(self, node_identifier: str) -> tuple[str, str]:
        """Resolve a node identifier to ``(nodeUUID, hostname)``.

        Args:
            node_identifier: Hostname or UUID.

        Returns:
            tuple[str, str]: Node UUID and hostname.

        Raises:
            ResourceNotFoundError: If the node is not in the cluster.

        Example:
            >>> client.resolve_node_uuid("node1.lan")
            ('uuid-1', 'node1.lan')
        """
        target = node_identifier.strip()
        nodes = self.get_cluster_nodes()
        for n in nodes:
            hostname = str(n.get("hostname") or "")
            uuid = str(n.get("nodeUUID") or n.get("nodeUuid") or "")
            if target.lower() in (hostname.lower(), uuid.lower()):
                return uuid, hostname
        raise ResourceNotFoundError(
            f"Cluster node '{node_identifier}' not found. "
            f"Available nodes: {', '.join(str(n.get('hostname')) for n in nodes)}"
        )

    def request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        files: Any = None,
        headers: dict[str, str] | None = None,
        node: str | None = None,
        require_auth: bool = True,
        unwrap_data: bool = True,
        resolve_node: bool = True,
    ) -> Any:
        """Send an HTTP request and unwrap the APIResponse envelope.

        Args:
            method: HTTP method.
            path: API path, without the ``/api`` prefix.
            params: Optional query parameters.
            json_body: Optional JSON request body.
            files: Optional multipart files.
            headers: Extra request headers.
            node: Target node hostname or UUID.
            require_auth: Send the bearer token and resolve node routing.
            unwrap_data: Return the ``data`` member of an APIResponse.
            resolve_node: Resolve the target node header before sending.

        Returns:
            Any: Unwrapped response data, or the full response when not unwrapped.

        Raises:
            SessionExpiredError: If authentication is missing or rejected.
            SylveAPIError: If the API returns an error status or payload.
            SylveError: If the connection fails.

        Example:
            >>> client.request("GET", "/cluster")
        """
        req_headers: dict[str, str] = {"Accept": "application/json"}
        if require_auth:
            self._ensure_valid_token()
            req_headers["Authorization"] = f"Bearer {self.context.token}"

        resolved_host = self.resolve_node_hostname(node) if require_auth and resolve_node else None
        if resolved_host:
            req_headers["X-Current-Hostname"] = resolved_host

        if headers:
            req_headers.update(headers)

        clean_params: dict[str, Any] | None = None
        if params:
            clean_params = {k: v for k, v in params.items() if v is not None}

        try:
            resp = self._http.request(
                method=method.upper(),
                url=path,
                params=clean_params,
                json=json_body,
                files=files,
                headers=req_headers,
            )
        except httpx.RequestError as exc:
            raise SylveError(f"Connection error talking to {self.context.server}: {exc}") from exc

        if resp.status_code == 401 and require_auth:
            raise SessionExpiredError(
                "Server rejected authentication token (HTTP 401 Unauthorized). "
                "Please re-authenticate with 'sylve login'."
            )

        payload: Any = None
        if resp.content:
            try:
                payload = resp.json()
            except ValueError:
                payload = resp.text

        if resp.status_code >= 400:
            err_code = ""
            err_data = None
            if isinstance(payload, dict):
                err_code = str(payload.get("error") or payload.get("message") or "")
                err_data = payload.get("data")
            raise SylveAPIError(
                message=_response_error_message(resp.status_code, payload, method.upper()),
                status_code=resp.status_code,
                error_code=err_code,
                data=err_data,
            )

        if isinstance(payload, dict) and payload.get("status") == "error":
            err_code = str(payload.get("error") or "")
            err_msg = str(payload.get("message") or err_code or "API Error")
            raise SylveAPIError(
                message=err_msg,
                status_code=resp.status_code,
                error_code=err_code,
                data=payload.get("data"),
            )

        if unwrap_data and isinstance(payload, dict) and "data" in payload:
            return payload["data"]
        return payload

    def get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        node: str | None = None,
        unwrap_data: bool = True,
    ) -> Any:
        return self.request("GET", path, params=params, node=node, unwrap_data=unwrap_data)

    def enrich_template_metadata(
        self, item: dict[str, Any], detail_path: str, node: str | None
    ) -> None:
        """Merge template-detail fields the simple list endpoints omit.

        The VM and jail ``SimpleTemplateList`` DTOs carry only id/name/source;
        the detail models add ``createdAt`` (and, for jails, ``pool``). Fetch
        the detail per template and merge whatever it supplies. A template that
        vanished mid-list keeps the list row as-is.
        """
        try:
            detail = self.get(detail_path, node=node)
        except SylveError:
            return
        if isinstance(detail, dict):
            for key in ("createdAt", "pool"):
                if detail.get(key) is not None:
                    item[key] = detail.get(key)

    def post(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        files: Any = None,
        node: str | None = None,
        unwrap_data: bool = True,
    ) -> Any:
        return self.request(
            "POST",
            path,
            params=params,
            json_body=json_body,
            files=files,
            node=node,
            unwrap_data=unwrap_data,
        )

    def download_file(
        self,
        path: str,
        destination: Path,
        *,
        params: dict[str, Any] | None = None,
        node: str | None = None,
    ) -> Path:
        """Stream a binary response to a local file.

        Args:
            path: API path.
            destination: Local file to write.
            params: Optional query parameters.
            node: Target node hostname or UUID.

        Returns:
            Path: The written file.

        Raises:
            SylveError: If the request fails.

        Example:
            >>> client.download_file("/certificates/1/archive", Path("cert.zip"))
        """
        self._ensure_valid_token()
        headers = {"Accept": "*/*", "Authorization": f"Bearer {self.context.token}"}
        resolved_host = self.resolve_node_hostname(node)
        if resolved_host:
            headers["X-Current-Hostname"] = resolved_host
        clean_params = {k: v for k, v in (params or {}).items() if v is not None}
        target = destination.expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        with self._http.stream(
            "GET", path, params=clean_params or None, headers=headers
        ) as response:
            if response.status_code >= 400:
                body: Any = None
                try:
                    body = response.json()
                except ValueError:
                    body = response.read().decode("utf-8", "replace")
                raise SylveError(
                    _response_error_message(response.status_code, body, f"downloading {path}")
                )
            with target.open("wb") as handle:
                for chunk in response.iter_bytes():
                    handle.write(chunk)
        return target

    def create_sse_token(self) -> str:
        """Mint a short-lived ``sse_token`` via ``POST /auth/sse-tokens``."""
        data = self.request("POST", "/auth/sse-tokens", resolve_node=False)
        if isinstance(data, dict) and data.get("token"):
            return str(data["token"])
        raise SylveError("Server did not return an sse_token from /auth/sse-tokens.")

    def stream_lines(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        node: str | None = None,
    ) -> Any:
        """Yield server-sent event lines from a streaming endpoint.

        When streaming ``/events/stream`` without an explicit ``sse_token``,
        automatically mints a short-lived capability via ``POST /auth/sse-tokens``.
        """
        self._ensure_valid_token()
        headers = {
            "Accept": "text/event-stream",
            "Authorization": f"Bearer {self.context.token}",
        }
        resolved_host = self.resolve_node_hostname(node)
        if resolved_host:
            headers["X-Current-Hostname"] = resolved_host
        clean_params = {k: v for k, v in (params or {}).items() if v is not None}
        if path == "/events/stream" and not clean_params.get("sse_token"):
            clean_params["sse_token"] = self.create_sse_token()
        with self._http.stream(
            "GET", path, params=clean_params or None, headers=headers
        ) as response:
            if response.status_code >= 400:
                body: Any = None
                try:
                    body = response.json()
                except ValueError:
                    body = response.read().decode("utf-8", "replace")
                raise SylveError(
                    _response_error_message(response.status_code, body, f"streaming {path}")
                )
            yield from response.iter_lines()

    def put(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        node: str | None = None,
        unwrap_data: bool = True,
    ) -> Any:
        return self.request(
            "PUT",
            path,
            params=params,
            json_body=json_body,
            node=node,
            unwrap_data=unwrap_data,
        )

    def patch(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        node: str | None = None,
        unwrap_data: bool = True,
    ) -> Any:
        return self.request(
            "PATCH",
            path,
            params=params,
            json_body=json_body,
            node=node,
            unwrap_data=unwrap_data,
        )

    def delete(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
        node: str | None = None,
        unwrap_data: bool = True,
    ) -> Any:
        return self.request(
            "DELETE",
            path,
            params=params,
            json_body=json_body,
            node=node,
            unwrap_data=unwrap_data,
        )

    # ------------------------------------------------------------------
    # Authentication helpers
    # ------------------------------------------------------------------
    def login(
        self,
        username: str,
        password: str,
        auth_type: str = "sylve",
        remember: bool = True,
    ) -> ContextConfig:
        """Authenticate and update the saved context.

        Args:
            username: Login name.
            password: Login password.
            auth_type: ``sylve`` or ``pam``.
            remember: Request a long-lived token.

        Returns:
            ContextConfig: Updated token and node metadata.

        Raises:
            SylveAPIError: If authentication fails.
            SylveError: If the request fails.

        Example:
            >>> client.login("admin", "secret")
        """
        data = self.request(
            "POST",
            "/auth/login",
            json_body={
                "username": username,
                "password": password,
                "authType": auth_type,
                "remember": remember,
            },
            require_auth=False,
        )
        if not isinstance(data, dict) or not data.get("token"):
            raise SylveError("Login response did not contain a valid token.")

        token = str(data["token"])
        self.context.username = username
        self.context.auth_type = auth_type
        self.context.token = token
        self.context.hostname = str(data.get("hostname") or "")
        self.context.node_id = str(data.get("nodeId") or "")
        self.context.expires_at = extract_token_expiry(token)
        return self.context

    def logout(self) -> None:
        """Revoke the active token when it is still valid.

        Returns:
            None.

        Example:
            >>> client.logout()
        """
        if self.context.token and not self.context.is_token_expired():
            try:
                self.post("/auth/logout")
            except SylveError:
                pass

    # ------------------------------------------------------------------
    # Cluster & Multi-Node Discovery
    # ------------------------------------------------------------------
    def get_cluster_nodes(self, refresh: bool = False) -> list[dict[str, Any]]:
        """Return cluster nodes, falling back to local node information.

        Args:
            refresh: Ignore the in-process cache.

        Returns:
            list[dict[str, Any]]: Node records.

        Example:
            >>> client.get_cluster_nodes()
        """
        if self._nodes_cache is not None and not refresh:
            return self._nodes_cache

        nodes: list[dict[str, Any]] = []
        try:
            raw = self.request("GET", "/cluster/nodes", node=None, resolve_node=False)
            if isinstance(raw, list):
                nodes = [n for n in raw if isinstance(n, dict)]
        except SylveError:
            nodes = []

        if not nodes:
            try:
                info = self.request("GET", "/info/node", node=None, resolve_node=False)
                if isinstance(info, dict):
                    nodes = [
                        {
                            "nodeUUID": self.context.node_id or "local",
                            "hostname": info.get("hostname")
                            or self.context.hostname
                            or "localhost",
                            "status": "online",
                            "cpu": info.get("logicalCores") or 0,
                            "cpuUsage": info.get("cpuUsage") or 0.0,
                            "memory": info.get("ramTotal") or 0,
                            "memoryUsage": info.get("ramUsage") or 0.0,
                            "disk": info.get("diskTotal") or 0,
                            "diskUsage": info.get("diskUsage") or 0.0,
                            "guestIDs": info.get("guestIds") or [],
                            "sylveVersion": info.get("sylveVersion") or "",
                            "sylveCommit": info.get("sylveCommit") or "",
                        }
                    ]
            except SylveError:
                if self.context.hostname:
                    nodes = [
                        {
                            "nodeUUID": self.context.node_id or "local",
                            "hostname": self.context.hostname,
                            "status": "online",
                        }
                    ]

        self._nodes_cache = nodes
        return nodes

    def get_online_nodes(self, refresh: bool = False) -> list[dict[str, Any]]:
        """Return online cluster nodes.

        Args:
            refresh: Ignore the in-process cache.

        Returns:
            list[dict[str, Any]]: Online node records.

        Example:
            >>> client.get_online_nodes()
        """
        nodes = self.get_cluster_nodes(refresh=refresh)
        online = [n for n in nodes if str(n.get("status") or "online").strip().lower() == "online"]
        return online or nodes

    def get_cluster_resources(self, refresh: bool = False) -> list[dict[str, Any]]:
        """Return per-node VM, Jail, and template resources.

        Args:
            refresh: Ignore the in-process cache.

        Returns:
            list[dict[str, Any]]: Per-node resource records.

        Example:
            >>> client.get_cluster_resources()
        """
        if self._resources_cache is not None and not refresh:
            return self._resources_cache

        resources: list[dict[str, Any]] = []
        try:
            raw = self.request("GET", "/cluster/resources", node=None)
            if isinstance(raw, list):
                resources = [r for r in raw if isinstance(r, dict)]
        except SylveError:
            resources = []

        if not resources:
            # Standalone fallback: query local /vm/simple and /jail/simple
            vms = []
            jails = []
            try:
                v_raw = self.get("/vm/simple")
                if isinstance(v_raw, list):
                    vms = v_raw
            except SylveError:
                pass
            try:
                j_raw = self.get("/jail/simple")
                if isinstance(j_raw, list):
                    jails = j_raw
            except SylveError:
                pass
            hostname = self.context.hostname or "localhost"
            nodes = self.get_cluster_nodes()
            if nodes and nodes[0].get("hostname"):
                hostname = str(nodes[0]["hostname"])
            resources = [
                {
                    "nodeUUID": self.context.node_id or "local",
                    "hostname": hostname,
                    "vms": vms,
                    "jails": jails,
                    "vmTemplates": [],
                    "jailTemplates": [],
                }
            ]

        self._resources_cache = resources
        return resources

    def fan_out_get(
        self,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        node: str | None = None,
    ) -> list[tuple[str, Any]]:
        """Execute a GET request across one node or all online nodes.

        Args:
            path: API path.
            params: Optional query parameters.
            node: Optional target node.

        Returns:
            list[tuple[str, Any]]: ``(hostname, response)`` pairs.

        Example:
            >>> client.fan_out_get("/vm/simple")
        """
        target = self.resolve_node_hostname(node)
        if target:
            data = self.get(path, params=params, node=target)
            return [(target, data)]

        online_nodes = self.get_online_nodes()
        if len(online_nodes) <= 1:
            host = (
                str(online_nodes[0].get("hostname"))
                if online_nodes and online_nodes[0].get("hostname")
                else (self.context.hostname or "local")
            )
            data = self.get(path, params=params, node=None)
            return [(host, data)]

        results: list[tuple[int, str, Any]] = []
        with ThreadPoolExecutor(max_workers=min(8, len(online_nodes))) as pool:
            futures = {
                pool.submit(self.get, path, params=params, node=str(n.get("hostname"))): (
                    idx,
                    str(n.get("hostname")),
                )
                for idx, n in enumerate(online_nodes)
                if n.get("hostname")
            }
            for fut in as_completed(futures):
                idx, host = futures[fut]
                try:
                    data = fut.result()
                    results.append((idx, host, data))
                except SylveError:
                    continue

        results.sort(key=lambda item: item[0])
        return [(host, data) for _, host, data in results]

    # ------------------------------------------------------------------
    # Guest-to-node resolvers
    # ------------------------------------------------------------------
    def resolve_vm(
        self,
        identifier: str | int,
        node: str | None = None,
    ) -> tuple[int, str, dict[str, Any]]:
        """Resolve a VM by RID or name.

        Args:
            identifier: Numeric RID or VM name.
            node: Optional node filter.

        Returns:
            tuple[int, str, dict[str, Any]]: RID, hostname, and summary.

        Raises:
            ResourceNotFoundError: If no VM matches.
            SylveError: If multiple VMs match.

        Example:
            >>> client.resolve_vm("web-01")
        """
        ident_str = str(identifier).strip()
        is_numeric = ident_str.isdigit()
        target_host = self.resolve_node_hostname(node)

        matches: list[tuple[int, str, dict[str, Any]]] = []
        for node_res in self.get_cluster_resources():
            host = str(node_res.get("hostname") or "")
            if target_host and host.lower() != target_host.lower():
                continue
            for vm in node_res.get("vms") or []:
                if not isinstance(vm, dict):
                    continue
                rid = vm.get("rid")
                name = str(vm.get("name") or "")
                if (
                    (is_numeric and str(rid) == ident_str) or (name.lower() == ident_str.lower())
                ) and rid is not None:
                    matches.append((int(rid), host, vm))

        if not matches and target_host:
            # Try querying the target node directly
            try:
                vms = self.get("/vm/simple", node=target_host)
                if isinstance(vms, list):
                    for vm in vms:
                        rid = vm.get("rid")
                        name = str(vm.get("name") or "")
                        if (
                            (is_numeric and str(rid) == ident_str)
                            or (name.lower() == ident_str.lower())
                        ) and rid is not None:
                            matches.append((int(rid), target_host, vm))
            except SylveError:
                pass

        if not matches and is_numeric:
            # Fallback if cluster resources didn't list it yet
            return int(ident_str), target_host or self.context.hostname or "", {}

        if not matches:
            scope = f" on node '{target_host}'" if target_host else " in cluster"
            raise ResourceNotFoundError(f"VM '{identifier}' not found{scope}.")

        if len(matches) > 1:
            locs = ", ".join(f"{m[2].get('name')}(rid={m[0]}, node={m[1]})" for m in matches)
            raise SylveError(
                f"Multiple VMs match '{identifier}': {locs}. "
                "Specify the numeric RID or pass '--node <hostname>'."
            )

        return matches[0]

    def resolve_jail(
        self,
        identifier: str | int,
        node: str | None = None,
    ) -> tuple[int, str, dict[str, Any]]:
        """Resolve a Jail by CTID or name.

        Args:
            identifier: Numeric CTID or Jail name.
            node: Optional node filter.

        Returns:
            tuple[int, str, dict[str, Any]]: CTID, hostname, and summary.

        Raises:
            ResourceNotFoundError: If no Jail matches.
            SylveError: If multiple Jails match.

        Example:
            >>> client.resolve_jail("app")
        """
        ident_str = str(identifier).strip()
        is_numeric = ident_str.isdigit()
        target_host = self.resolve_node_hostname(node)

        matches: list[tuple[int, str, dict[str, Any]]] = []
        for node_res in self.get_cluster_resources():
            host = str(node_res.get("hostname") or "")
            if target_host and host.lower() != target_host.lower():
                continue
            for jail in node_res.get("jails") or []:
                if not isinstance(jail, dict):
                    continue
                ctid = jail.get("ctId")
                name = str(jail.get("name") or "")
                if (
                    (is_numeric and str(ctid) == ident_str) or (name.lower() == ident_str.lower())
                ) and ctid is not None:
                    matches.append((int(ctid), host, jail))

        if not matches and target_host:
            try:
                jails = self.get("/jail/simple", node=target_host)
                if isinstance(jails, list):
                    for jail in jails:
                        ctid = jail.get("ctId")
                        name = str(jail.get("name") or "")
                        if (
                            (is_numeric and str(ctid) == ident_str)
                            or (name.lower() == ident_str.lower())
                        ) and ctid is not None:
                            matches.append((int(ctid), target_host, jail))
            except SylveError:
                pass

        if not matches and is_numeric:
            return int(ident_str), target_host or self.context.hostname or "", {}

        if not matches:
            scope = f" on node '{target_host}'" if target_host else " in cluster"
            raise ResourceNotFoundError(f"Jail '{identifier}' not found{scope}.")

        if len(matches) > 1:
            locs = ", ".join(f"{m[2].get('name')}(ctid={m[0]}, node={m[1]})" for m in matches)
            raise SylveError(
                f"Multiple Jails match '{identifier}': {locs}. "
                "Specify the numeric CTID or pass '--node <hostname>'."
            )

        return matches[0]
