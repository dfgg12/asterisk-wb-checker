"""Minimal AMI client to originate HD test calls."""

from __future__ import annotations

import logging
import socket
import time
from dataclasses import dataclass

LOG = logging.getLogger(__name__)
AMI_TIMEOUT_S = 30.0


class AmiError(RuntimeError):
    """AMI login or action failure."""


@dataclass(slots=True)
class AmiConfig:
    """Connection settings for Asterisk Manager Interface."""

    host: str = "127.0.0.1"
    port: int = 5038
    username: str = "wbchecker"
    secret: str = ""


class AmiClient:
    """Blocking single-action AMI client, enough for Originate."""

    def __init__(self, cfg: AmiConfig) -> None:
        self.cfg = cfg
        self.sock: socket.socket | None = None
        self._buf = b""

    def __enter__(self) -> "AmiClient":
        self.sock = socket.create_connection(
            (self.cfg.host, self.cfg.port), timeout=AMI_TIMEOUT_S)
        self._read_line()  # banner
        resp = self.action("Login", Username=self.cfg.username,
                           Secret=self.cfg.secret)
        if resp.get("Response") != "Success":
            raise AmiError(f"AMI login failed: {resp}")
        return self

    def __exit__(self, *exc: object) -> None:
        if self.sock is not None:
            try:
                self.action("Logoff")
            except (OSError, AmiError):
                pass
            self.sock.close()
            self.sock = None

    def _read_line(self) -> str:
        assert self.sock is not None
        while b"\r\n" not in self._buf:
            chunk = self.sock.recv(4096)
            if not chunk:
                raise AmiError("AMI connection closed")
            self._buf += chunk
        line, self._buf = self._buf.split(b"\r\n", 1)
        return line.decode("utf-8", "replace")

    def _read_packet(self) -> dict[str, str]:
        packet: dict[str, str] = {}
        while (line := self._read_line()):
            key, _, value = line.partition(":")
            packet[key.strip()] = value.strip()
        return packet

    def action(self, name: str, **headers: str) -> dict[str, str]:
        """Send one AMI action, return its Response packet."""
        assert self.sock is not None
        lines = [f"Action: {name}"]
        lines += [f"{k}: {v}" for k, v in headers.items()]
        self.sock.sendall(
            ("\r\n".join(lines) + "\r\n\r\n").encode())
        # Skip async events until a Response packet arrives.
        deadline = time.monotonic() + AMI_TIMEOUT_S
        while time.monotonic() < deadline:
            packet = self._read_packet()
            if "Response" in packet:
                return packet
        raise AmiError(f"timeout waiting for response to {name}")


def originate_test_call(cfg: AmiConfig, channel: str,
                        context: str = "hd-test",
                        exten: str = "record",
                        timeout_ms: int = 30000) -> None:
    """Originate: dial channel, on answer send it to recorder exten.

    channel example: PJSIP/48123456789@testtrunk
    Far end must answer into something that plays the probe tone
    (your own extension 8000, an echo test, or a peer PBX).
    """
    with AmiClient(cfg) as ami:
        resp = ami.action(
            "Originate",
            Channel=channel,
            Context=context,
            Exten=exten,
            Priority="1",
            Timeout=str(timeout_ms),
            Async="false",
        )
        if resp.get("Response") != "Success":
            raise AmiError(f"Originate failed: {resp}")
        LOG.info("[INFO] originate ok: %s -> %s@%s",
                 channel, exten, context)
