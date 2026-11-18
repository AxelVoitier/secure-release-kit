# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Stand-in index for local tests: PyPI JSON API (per version), PEP 503 simple, files. No integrity API.
usage: miniindex.py DIR PORT   (pypiserver 2.4 has no JSON API, which the hash rule and verify need)"""
import hashlib, http.server, json, os, re, sys

D, PORT = sys.argv[1], int(sys.argv[2])
norm = lambda n: re.sub(r"[-_.]+", "-", n).lower()


def files(name, ver=None):
    out = []
    for f in sorted(os.listdir(D)):
        m = re.match(r"(.+?)-([^-]+?)(\.tar\.gz|-.*\.whl)$", f)
        if m and norm(m.group(1)) == norm(name) and (ver is None or m.group(2) == ver):
            h = hashlib.sha256(open(os.path.join(D, f), "rb").read()).hexdigest()
            out.append({"filename": f, "url": f"http://localhost:{PORT}/packages/{f}", "digests": {"sha256": h}})
    return out


class H(http.server.BaseHTTPRequestHandler):
    def send(self, code, body, ctype):
        self.send_response(code); self.send_header("Content-Type", ctype); self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        p = self.path.split("?")[0].strip("/").split("/")
        if p[0] == "pypi" and len(p) == 4 and p[3] == "json":
            fs = files(p[1], p[2])
            return self.send(200, json.dumps({"info": {"name": p[1], "version": p[2]}, "urls": fs}).encode(), "application/json") if fs else self.send(404, b"{}", "application/json")
        if p[0] == "simple" and len(p) == 2:
            links = "".join(f'<a href="{f["url"]}#sha256={f["digests"]["sha256"]}">{f["filename"]}</a>\n' for f in files(p[1]))
            return self.send(200 if links else 404, f"<html><body>{links}</body></html>".encode(), "text/html")
        if p[0] == "packages" and len(p) == 2 and os.path.exists(os.path.join(D, p[1])):
            return self.send(200, open(os.path.join(D, p[1]), "rb").read(), "application/octet-stream")
        self.send(404, b"not found", "text/plain")

    def log_message(self, *a): pass


http.server.ThreadingHTTPServer(("127.0.0.1", PORT), H).serve_forever()
