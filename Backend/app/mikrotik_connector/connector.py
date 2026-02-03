import os
import asyncio
from typing import Optional, Dict, List

from librouteros import connect
from librouteros.exceptions import LibRouterosError
import paramiko


class MikroTikConnector:
    def __init__(
        self,
        host: str,
        username: str,
        password: str,
        api_port: int = 8728,
        ssh_port: int = 22,
        use_ssl: bool = False,
        api_timeout: int = 5,
    ):
        self.host = host
        self.username = username
        self.password = password

        self.api_port = api_port
        self.ssh_port = ssh_port
        self.use_ssl = use_ssl
        self.api_timeout = api_timeout

        self.api_connection = None
        self.ssh_client = None
        self.sftp_client = None

    # ------------------------------------------------------------------
    # CONNECTION MANAGEMENT
    # ------------------------------------------------------------------

    async def connect(self):
        """
        Подключение:
        - пытаемся API
        - SSH подключаем независимо (fallback)
        """
        await self._connect_api()
        self._connect_ssh()

    async def disconnect(self):
        await self._disconnect_api()
        self._disconnect_ssh()

    # ---------------- API ---------------- #

    async def _connect_api(self):
        loop = asyncio.get_event_loop()

        try:
            self.api_connection = await loop.run_in_executor(
                None,
                lambda: connect(
                    host=self.host,
                    username=self.username,
                    password=self.password,
                    port=self.api_port,
                    use_ssl=self.use_ssl,
                    timeout=self.api_timeout,
                ),
            )
            print(f"[API] Connected to {self.host}")
        except Exception as e:
            self.api_connection = None
            print(f"[API] Connection failed: {e}")

    async def _disconnect_api(self):
        try:
            if self.api_connection:
                self.api_connection.close()
        finally:
            self.api_connection = None
            print(f"[API] Disconnected from {self.host}")

    # ---------------- SSH ---------------- #

    def _connect_ssh(self):
        try:
            self.ssh_client = paramiko.SSHClient()
            self.ssh_client.set_missing_host_key_policy(
                paramiko.AutoAddPolicy()
            )
            self.ssh_client.connect(
                hostname=self.host,
                port=self.ssh_port,
                username=self.username,
                password=self.password,
                look_for_keys=False,
                allow_agent=False,
                timeout=10,
            )
            self.sftp_client = self.ssh_client.open_sftp()
            print(f"[SSH] Connected to {self.host}")
        except Exception as e:
            self.ssh_client = None
            self.sftp_client = None
            print(f"[SSH] Connection failed: {e}")

    def _disconnect_ssh(self):
        try:
            if self.sftp_client:
                self.sftp_client.close()
            if self.ssh_client:
                self.ssh_client.close()
        finally:
            self.sftp_client = None
            self.ssh_client = None
            print(f"[SSH] Disconnected from {self.host}")

    # ------------------------------------------------------------------
    # UNIFIED ROUTEROS EXECUTION
    # ------------------------------------------------------------------

    async def ros_execute(
        self,
        path: str,
        *,
        action: str,
        params: Optional[Dict] = None,
        where: Optional[Dict] = None,
    ) -> List[Dict]:
        """
        Унифицированное выполнение RouterOS-команд.

        Сначала API → при ошибке fallback на SSH.

        path: "/ip/firewall/address-list"
        action: print | add | remove
        """
        params = params or {}
        where = where or {}

        # 1. API
        if self.api_connection:
            try:
                return await self._execute_api(path, action, params, where)
            except Exception as e:
                print(f"[ROS] API failed, fallback to SSH: {e}")

        # 2. SSH fallback
        if self.ssh_client:
            return self._execute_ssh(path, action, params, where)

        raise RuntimeError("No available API or SSH connection")

    # ------------------------------------------------------------------
    # API IMPLEMENTATION
    # ------------------------------------------------------------------

    async def _execute_api(
            self,
            path: str,
            action: str,
            params: Dict,
            where: Dict,
    ) -> List[Dict]:
        loop = asyncio.get_event_loop()

        def _call():
            if action == "print":
                if where:
                    return list(self.api_connection(f"{path}/print", where=where))
                else:
                    return list(self.api_connection(f"{path}/print"))

            elif action == "add":
                if params:
                    self.api_connection(f"{path}/add", **params)
                else:
                    self.api_connection(f"{path}/add")
                return []

            elif action == "remove":
                if params:
                    self.api_connection(f"{path}/remove", **params)
                else:
                    raise ValueError("Missing parameters for remove")
                return []

            else:
                raise ValueError(f"Unsupported action: {action}")

        try:
            return await loop.run_in_executor(None, _call)
        except LibRouterosError as e:
            raise RuntimeError(f"API error: {e}") from e

    # ------------------------------------------------------------------
    # SSH IMPLEMENTATION (CLI)
    # ------------------------------------------------------------------

    def _execute_ssh(
        self,
        path: str,
        action: str,
        params: Dict,
        where: Dict,
    ) -> List[Dict]:
        base = path.strip("/").replace("/", " ")

        if action == "print":
            cmd = f"/{base} print"
            out, err = self._run_ssh(cmd)
            if err:
                raise RuntimeError(err)
            return self._parse_print(out)

        elif action == "add":
            args = " ".join(f"{k}={v}" for k, v in params.items())
            cmd = f"/{base} add {args}"
            self._run_ssh(cmd)
            return []

        elif action == "remove":
            if ".id" not in params:
                raise ValueError("Missing .id for remove")
            cmd = f"/{base} remove {params['.id']}"
            self._run_ssh(cmd)
            return []

        else:
            raise ValueError(f"Unsupported action: {action}")

    def _run_ssh(self, command: str):
        if not self.ssh_client:
            raise RuntimeError("SSH connection not established")
        stdin, stdout, stderr = self.ssh_client.exec_command(command)
        return stdout.read().decode(), stderr.read().decode()

    def run_ssh_command(self, command: str) -> str:
        output, error = self._run_ssh(command)
        if error:
            raise RuntimeError(error)
        return output

    # ------------------------------------------------------------------
    # PARSING (minimal, safe)
    # ------------------------------------------------------------------

    def _parse_print(self, output: str) -> List[Dict]:
        """
        Минимальный парсер print-вывода.
        Для fallback-режима.
        """
        items = []
        for line in output.splitlines():
            if "=" not in line:
                continue
            entry = {}
            for part in line.split():
                if "=" in part:
                    k, v = part.split("=", 1)
                    entry[k] = v
            if entry:
                items.append(entry)
        return items

    # ------------------------------------------------------------------
    # FILE OPERATIONS (SSH ONLY)
    # ------------------------------------------------------------------

    def upload_file(self, local_path: str, remote_path: str):
        if not self.sftp_client:
            raise RuntimeError("SFTP not connected")
        if not os.path.isfile(local_path):
            raise FileNotFoundError(local_path)
        self.sftp_client.put(local_path, remote_path)

    def download_file(self, remote_path: str, local_path: str):
        if not self.sftp_client:
            raise RuntimeError("SFTP not connected")
        self.sftp_client.get(remote_path, local_path)
