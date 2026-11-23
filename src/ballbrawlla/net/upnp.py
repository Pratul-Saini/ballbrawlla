"""Ask the home router to open the game's port (UPnP), so players on other networks can connect.

Most home routers let a program on the network open a port for itself (UPnP "Internet Gateway Device").
`PortOpener` does that in a background thread while a game is hosted, renews it, and closes it again when
the game ends. It never raises: when the router can't or won't, `state` becomes "failed" with a reason a
player can act on. Only the standard library is used.

    discover   UDP multicast M-SEARCH to 239.255.255.250:1900, read LOCATION from the answers
    describe   GET the router's description XML, find the WANIPConnection / WANPPPConnection control URL
    control    SOAP: GetExternalIPAddress, AddPortMapping, DeletePortMapping

A router's public address that is itself private (10.x, 192.168.x, 100.64.x ...) means another router or
the internet provider sits in front of it (double NAT / carrier NAT): opening a port on this router then
doesn't make the game reachable, so that is reported as a failure too.
"""

from __future__ import annotations

import ipaddress
import re
import socket
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree

SSDP_ADDR = ("239.255.255.250", 1900)
SEARCH_TARGETS = (
    "urn:schemas-upnp-org:device:InternetGatewayDevice:1",
    "urn:schemas-upnp-org:device:InternetGatewayDevice:2",
    "urn:schemas-upnp-org:service:WANIPConnection:1",
    "urn:schemas-upnp-org:service:WANIPConnection:2",
    "urn:schemas-upnp-org:service:WANPPPConnection:1",
)
SERVICES = ("WANIPConnection", "WANPPPConnection")
DESCRIPTION = "Gridiron Scramble"
LEASE = 3600            # seconds; renewed every RENEW while hosting, so a crash doesn't leave it open for long
RENEW = 1500
MAX_BODY = 256 * 1024

FIX = ("To fix it, turn on UPnP in your router's settings, or forward TCP port {port} to {ip}. "
       "Players on the same Wi-Fi can join either way.")


class UpnpError(Exception):
    """Something a player can read."""


def _http(url: str, data: bytes | None = None, headers: dict | None = None, timeout: float = 3.0) -> bytes:
    req = urllib.request.Request(url, data=data, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read(MAX_BODY)
    except urllib.error.HTTPError as e:      # SOAP faults come back as HTTP 500 with a body
        return e.read(MAX_BODY) if e.code == 500 else b""


def discover(lan_ip: str, wait: float = 2.5) -> list[str]:
    """LOCATION URLs of the gateways that answered an SSDP search (on the network `lan_ip` is on)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        try:
            sock.bind((lan_ip, 0))
        except OSError:
            sock.bind(("", 0))
        for st in SEARCH_TARGETS:
            msg = (f"M-SEARCH * HTTP/1.1\r\nHOST: {SSDP_ADDR[0]}:{SSDP_ADDR[1]}\r\nMAN: \"ssdp:discover\"\r\n"
                   f"MX: 2\r\nST: {st}\r\n\r\n").encode()
            try:
                sock.sendto(msg, SSDP_ADDR)
            except OSError:
                pass
        found: list[str] = []
        deadline = time.monotonic() + wait
        while (left := deadline - time.monotonic()) > 0:
            sock.settimeout(left)
            try:
                data, _ = sock.recvfrom(4096)
            except (socket.timeout, OSError):
                break
            m = re.search(rb"^location:\s*(\S+)", data, re.IGNORECASE | re.MULTILINE)
            if m:
                url = m.group(1).decode(errors="replace")
                if url.startswith("http://") and url not in found:
                    found.append(url)
        return found
    finally:
        sock.close()


def control_url(location: str) -> tuple[str, str] | None:
    """(control URL, service type) of the router's WAN connection service, from its description."""
    try:
        root = ElementTree.fromstring(_http(location))
    except (ElementTree.ParseError, OSError, ValueError):
        return None
    base = next((e.text.strip() for e in root.iter() if e.tag.endswith("URLBase") and e.text), "") or location
    for svc in root.iter():
        if not svc.tag.endswith("service"):
            continue
        fields = {child.tag.rsplit("}", 1)[-1]: (child.text or "").strip() for child in svc}
        stype = fields.get("serviceType", "")
        if any(name in stype for name in SERVICES) and fields.get("controlURL"):
            url = urljoin(base, fields["controlURL"])
            if urlsplit(url).scheme == "http":
                return url, stype
    return None


def soap(url: str, service: str, action: str, args: dict[str, object], timeout: float = 3.0) -> dict[str, str]:
    """Call `action`; returns the response's fields. Raises UpnpError with the router's error code."""
    body = "".join(f"<{k}>{v}</{k}>" for k, v in args.items())
    envelope = ('<?xml version="1.0"?><s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" '
                's:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"><s:Body>'
                f'<u:{action} xmlns:u="{service}">{body}</u:{action}></s:Body></s:Envelope>').encode()
    headers = {"Content-Type": 'text/xml; charset="utf-8"', "SOAPAction": f'"{service}#{action}"'}
    try:
        raw = _http(url, envelope, headers, timeout)
        root = ElementTree.fromstring(raw)
    except (OSError, ValueError, ElementTree.ParseError) as e:
        raise UpnpError(f"the router didn't answer ({e})") from e
    fields = {e.tag.rsplit("}", 1)[-1]: (e.text or "").strip() for e in root.iter()}
    if "errorCode" in fields:
        raise UpnpError(fields["errorCode"])
    return fields


def is_public(ip: str) -> bool:
    try:
        addr = ipaddress.IPv4Address(ip)
    except ValueError:
        return False
    return not (addr.is_private or addr.is_loopback or addr.is_link_local or addr.is_unspecified
                or addr in ipaddress.IPv4Network("100.64.0.0/10"))


class PortOpener:
    """Opens TCP `port` on the router for this computer (`lan_ip`), in a thread. Poll `state`:
    "checking", then "open" (with `public_ip`) or "failed" (with `reason`). close() removes the mapping."""

    def __init__(self, port: int, lan_ip: str, start: bool = True) -> None:
        self.port, self.lan_ip = port, lan_ip
        self.state = "checking"
        self.public_ip = ""
        self.reason = ""
        self._ctrl: tuple[str, str] | None = None
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="upnp", daemon=True)
        if start:
            self._thread.start()

    def _fail(self, why: str) -> None:
        self.reason = f"{why} {FIX.format(port=self.port, ip=self.lan_ip)}"
        self.state = "failed"

    def _run(self) -> None:
        try:
            self._open()
        except Exception as e:                  # never take the game down
            self._fail(f"Opening a port on your router failed ({e}).")
            return
        while self.state == "open" and not self._stop.wait(RENEW):
            try:
                self._map()
            except UpnpError:
                pass                            # keep the old mapping; it lasts LEASE seconds

    def _open(self) -> None:
        if self.lan_ip.startswith("127."):
            self._fail("This computer isn't connected to a network.")
            return
        for location in discover(self.lan_ip):
            self._ctrl = control_url(location)
            if self._ctrl:
                break
        if not self._ctrl:
            self._fail("Your router didn't answer the request to open a port (UPnP is off, or not supported).")
            return
        try:
            ext = soap(*self._ctrl, "GetExternalIPAddress", {}).get("NewExternalIPAddress", "")
        except UpnpError as e:
            self._fail(f"Your router didn't say what its internet address is (error {e}).")
            return
        if not is_public(ext):
            self._fail("Your router is behind another router, or your internet provider shares one address "
                       "between many homes, so players elsewhere can't reach this computer.")
            return
        try:
            self._map()
        except UpnpError as e:
            code = str(e)
            if code == "718":
                self._fail(f"Your router already gives port {self.port} to another computer on your network.")
            else:
                self._fail(f"Your router refused to open port {self.port} (error {code}).")
            return
        if self._stop.is_set():                 # closed while we were asking: undo it
            self._unmap()
            return
        self.public_ip = ext
        self.state = "open"

    def _map(self) -> None:
        args = {"NewRemoteHost": "", "NewExternalPort": self.port, "NewProtocol": "TCP",
                "NewInternalPort": self.port, "NewInternalClient": self.lan_ip, "NewEnabled": 1,
                "NewPortMappingDescription": DESCRIPTION, "NewLeaseDuration": LEASE}
        try:
            soap(*self._ctrl, "AddPortMapping", args)
        except UpnpError as e:
            if str(e) != "725":                 # OnlyPermanentLeasesSupported
                raise
            soap(*self._ctrl, "AddPortMapping", {**args, "NewLeaseDuration": 0})

    def _unmap(self) -> None:
        try:
            soap(*self._ctrl, "DeletePortMapping",
                 {"NewRemoteHost": "", "NewExternalPort": self.port, "NewProtocol": "TCP"}, timeout=1.5)
        except UpnpError:
            pass

    def close(self) -> None:
        self._stop.set()
        if self.state == "open" and self._ctrl:
            self.state = "closed"
            self._unmap()
