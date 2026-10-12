"""Loopback CalDAV provider used by the PSEBench conformance audit.

The service is deliberately small and protocol-facing.  It starts a pinned
Radicale process in a temporary storage directory, creates a real CalDAV
collection, and exposes only HTTP/CalDAV operations needed by the frozen
provider corpus.  The observer uses GET and calendar-query REPORT responses;
it does not call the IACG decision code.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import time
from typing import Mapping
from urllib import error as urlerror
from urllib import request as urlrequest
import xml.etree.ElementTree as ET


RUNTIME_VERSION = "radicale-3.7.8"
PRINCIPAL_PATH = "/alice/"
AUTHORIZED_COLLECTION = "/alice/authorized/"
ALTERNATE_COLLECTION = "/alice/alternate/"
REPORT_START = "20260824T000000Z"
REPORT_END = "20260910T000000Z"


@dataclass(frozen=True)
class HttpResponse:
    status: int
    headers: dict[str, str]
    body: bytes


@dataclass(frozen=True)
class EventState:
    path: str
    status: int
    uid: str
    summary: str
    recurrence: str
    event_count: int
    body_digest: str
    etag_present: bool


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _unfold_ical(body: bytes) -> list[str]:
    text = body.decode("utf-8", errors="replace").replace("\r\n", "\n")
    lines = text.split("\n")
    result: list[str] = []
    for line in lines:
        if line.startswith((" ", "\t")) and result:
            result[-1] += line[1:]
        elif line:
            result.append(line)
    return result


def parse_event(body: bytes) -> tuple[str, str, str]:
    """Return UID, summary, and RRULE without consulting policy code."""

    uid = ""
    summary = ""
    recurrence = ""
    for line in _unfold_ical(body):
        key, sep, value = line.partition(":")
        if not sep:
            continue
        name = key.split(";", 1)[0].upper()
        if name == "UID":
            uid = value.strip()
        elif name == "SUMMARY":
            summary = value.strip()
        elif name == "RRULE":
            recurrence = value.strip()
    return uid, summary, recurrence


def event_body(
    uid: str,
    summary: str,
    *,
    recurrence: str = "",
    variant: str = "canonical",
) -> bytes:
    """Build a deterministic VEVENT with optional provider-normalization cues."""

    fields = [
        f"UID:{uid}",
        "DTSTAMP:20260824T140000Z",
        "DTSTART:20260825T140000Z",
    ]
    if recurrence:
        fields.append(f"RRULE:{recurrence}")
    fields.append(f"SUMMARY:{summary}")
    if variant == "reordered":
        fields = [fields[0], fields[-1], *fields[1:-1]]
    elif variant == "folded-summary":
        fields[-1] = "SUMMARY:" + summary[:5]
        fields.append(" " + summary[5:])
    return (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//PSEBench//CalDAV//EN\r\n"
        "BEGIN:VEVENT\r\n"
        + "\r\n".join(fields)
        + "\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n"
    ).encode("utf-8")


def _digest(body: bytes) -> str:
    import hashlib

    return hashlib.sha256(body).hexdigest()


class RadicaleCalDAVServer:
    """Ephemeral local Radicale server for one isolated audit trial."""

    def __init__(self, runtime_path: Path):
        self.runtime_path = runtime_path
        self._tmp: tempfile.TemporaryDirectory[str] | None = None
        self._process: subprocess.Popen[str] | None = None
        self.port = 0
        self.base_url = ""

    def __enter__(self) -> "RadicaleCalDAVServer":
        self._tmp = tempfile.TemporaryDirectory(prefix="psebench-caldav-")
        storage = Path(self._tmp.name) / "storage"
        storage.mkdir()
        self.port = _free_port()
        env = dict(os.environ)
        prior = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (
            str(self.runtime_path)
            if not prior
            else f"{self.runtime_path}{os.pathsep}{prior}"
        )
        command = [
            "python3",
            "-m",
            "radicale",
            "-H",
            f"127.0.0.1:{self.port}",
            "--auth-type",
            "none",
            "--rights-type",
            "owner_only",
            "--storage-filesystem-folder",
            str(storage),
            "--logging-level",
            "warning",
        ]
        self._process = subprocess.Popen(
            command,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        self.base_url = f"http://127.0.0.1:{self.port}"
        for _ in range(100):
            if self._process.poll() is not None:
                raise RuntimeError("Radicale exited before becoming ready")
            try:
                response = self.request("OPTIONS", "/")
                if response.status == 200:
                    break
            except OSError:
                pass
            time.sleep(0.05)
        else:
            raise RuntimeError("Radicale did not become ready")
        self._create_collections()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._process is not None:
            self._process.terminate()
            try:
                self._process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=3)
        if self._tmp is not None:
            self._tmp.cleanup()

    def request(
        self,
        method: str,
        path: str,
        body: bytes = b"",
        headers: Mapping[str, str] | None = None,
    ) -> HttpResponse:
        request = urlrequest.Request(
            self.base_url + path,
            data=body if body else None,
            headers=dict(headers or {}),
            method=method,
        )
        try:
            with urlrequest.urlopen(request, timeout=3) as response:
                return HttpResponse(
                    int(response.status),
                    {key.lower(): value for key, value in response.headers.items()},
                    response.read(),
                )
        except urlerror.HTTPError as exc:
            return HttpResponse(
                int(exc.code),
                {key.lower(): value for key, value in exc.headers.items()},
                exc.read(),
            )

    def _create_collections(self) -> None:
        principal = (
            b'<mkcol xmlns="DAV:"><set><prop>'
            b"<resourcetype><collection/></resourcetype>"
            b"</prop></set></mkcol>"
        )
        calendar = (
            b'<mkcol xmlns="DAV:" xmlns:C="urn:ietf:params:xml:ns:caldav">'
            b"<set><prop><resourcetype><collection/><C:calendar/>"
            b"</resourcetype><C:supported-calendar-component-set>"
            b'<C:comp name="VEVENT"/></C:supported-calendar-component-set>'
            b"</prop></set></mkcol>"
        )
        for path in (PRINCIPAL_PATH,):
            response = self.request(
                "MKCOL", path, principal, {"Content-Type": "application/xml"}
            )
            if response.status not in {201, 405}:
                raise RuntimeError(f"failed to create principal: {response.status}")
        for path in (AUTHORIZED_COLLECTION, ALTERNATE_COLLECTION):
            response = self.request(
                "MKCALENDAR", path, calendar, {"Content-Type": "application/xml"}
            )
            if response.status not in {201, 405}:
                raise RuntimeError(f"failed to create calendar: {response.status}")

    def put(
        self,
        collection: str,
        uid: str,
        body: bytes,
        *,
        if_match: str | None = None,
        if_none_match: str | None = None,
    ) -> HttpResponse:
        headers = {"Content-Type": "text/calendar; charset=utf-8"}
        if if_match is not None:
            headers["If-Match"] = if_match
        if if_none_match is not None:
            headers["If-None-Match"] = if_none_match
        return self.request("PUT", f"{collection}{uid}.ics", body, headers)

    def get(self, collection: str, uid: str) -> HttpResponse:
        return self.request("GET", f"{collection}{uid}.ics")

    def expanded_report(self, collection: str) -> HttpResponse:
        body = (
            f'<C:calendar-query xmlns:D="DAV:" '
            f'xmlns:C="urn:ietf:params:xml:ns:caldav">'
            f"<D:prop><C:calendar-data><C:expand start=\"{REPORT_START}\" "
            f"end=\"{REPORT_END}\"/></C:calendar-data></D:prop>"
            f'<C:filter><C:comp-filter name="VCALENDAR">'
            f'<C:comp-filter name="VEVENT"/></C:comp-filter></C:filter>'
            f"</C:calendar-query>"
        ).encode("utf-8")
        return self.request(
            "REPORT",
            collection,
            body,
            {"Depth": "1", "Content-Type": "application/xml"},
        )

    def observe(self, collection: str, uid: str) -> EventState:
        response = self.get(collection, uid)
        if response.status != 200:
            return EventState(
                collection,
                response.status,
                "",
                "",
                "",
                0,
                "",
                False,
            )
        parsed_uid, summary, recurrence = parse_event(response.body)
        event_count = 1
        if recurrence:
            report = self.expanded_report(collection)
            event_count = 0
            if report.status == 207:
                try:
                    root = ET.fromstring(report.body)
                    event_count = sum(
                        (element.text or "").count("BEGIN:VEVENT")
                        for element in root.iter()
                        if element.tag.endswith("calendar-data")
                    )
                except ET.ParseError:
                    event_count = 0
        return EventState(
            collection,
            response.status,
            parsed_uid,
            summary,
            recurrence,
            event_count,
            _digest(response.body),
            "etag" in response.headers,
        )
