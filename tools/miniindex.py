# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Serve local test distributions through the PyPI JSON and simple index APIs."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar, TypedDict

DISTRIBUTION = re.compile(r'(.+?)-([^-]+?)(\.tar\.gz|-.*\.whl)$')


class IndexFile(TypedDict):
    filename: str
    url: str
    digests: dict[str, str]


def normalized(name: str) -> str:
    return re.sub(r'[-_.]+', '-', name).lower()


class IndexHandler(BaseHTTPRequestHandler):
    directory: ClassVar[Path]
    port: ClassVar[int]

    def distributions(self, project: str, version: str | None = None) -> list[IndexFile]:
        files: list[IndexFile] = []
        for path in sorted(self.directory.iterdir()):
            match = DISTRIBUTION.fullmatch(path.name)
            if not match or normalized(match[1]) != normalized(project):
                continue
            if version is not None and match[2] != version:
                continue
            files.append(
                IndexFile(
                    filename=path.name,
                    url=f'http://localhost:{self.port}/packages/{path.name}',
                    digests={'sha256': hashlib.sha256(path.read_bytes()).hexdigest()},
                )
            )
        return files

    def reply(self, status: HTTPStatus, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        route = self.path.partition('?')[0].strip('/').split('/')
        match route:
            case ['pypi', project, version, 'json']:
                files = self.distributions(project, version)
                if files:
                    body = {'info': {'name': project, 'version': version}, 'urls': files}
                    self.reply(HTTPStatus.OK, json.dumps(body).encode(), 'application/json')
                else:
                    self.reply(HTTPStatus.NOT_FOUND, b'{}', 'application/json')
            case ['simple', project]:
                files = self.distributions(project)
                links = ''.join(
                    f'<a href="{file["url"]}#sha256={file["digests"]["sha256"]}">'
                    f'{file["filename"]}</a>\n'
                    for file in files
                )
                status = HTTPStatus.OK if files else HTTPStatus.NOT_FOUND
                self.reply(status, f'<html><body>{links}</body></html>'.encode(), 'text/html')
            case ['packages', filename] if (self.directory / filename).is_file():
                self.reply(
                    HTTPStatus.OK,
                    (self.directory / filename).read_bytes(),
                    'application/octet-stream',
                )
            case _:
                self.reply(HTTPStatus.NOT_FOUND, b'not found', 'text/plain')

    # The HTTP handler accepts "format" as a keyword on Python 3.11.
    def log_message(  # pyright: ignore[reportImplicitOverride]
        self,
        format: str,  # noqa: A002
        *args: object,
    ) -> None:
        """Keep fixture requests out of the step under test's output."""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('port', type=int)
    args = parser.parse_args()
    IndexHandler.directory = args.directory
    IndexHandler.port = args.port
    with ThreadingHTTPServer(('127.0.0.1', args.port), IndexHandler) as server:
        server.serve_forever()


if __name__ == '__main__':
    main()
