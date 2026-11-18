# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Expand YAML anchors/aliases textually (act rejects aliases). Keeps comments. Indentation of
anchor and alias sites must match (true here: all steps sit at the same depth).
Also rewrites `uses: $/...` (self-repository form) to `uses: ./...`: act and actionlint 1.7.12 don't know `$/` yet.
For reusable-workflow calls both forms load the caller's commit, so the copy behaves the same.
MAINTAINER: drop that rewrite once act (and actionlint) accept `$/`.
Rewrites its argument IN PLACE: run it on a copy only."""
import re, sys
p = sys.argv[1]; lines = open(p).read().split("\n")
ind = lambda l: len(l) - len(l.lstrip(" "))
blocks = {}
for i, l in enumerate(lines):
    m = re.match(r"^(\s*)(- |steps: )&([\w-]+)\s*$", l)
    if not m: continue
    base = ind(l); j = i + 1
    while j < len(lines) and (lines[j].strip() == "" or ind(lines[j]) > base): j += 1
    while lines[j - 1].strip() == "": j -= 1
    blocks[m.group(3)] = (m.group(2), lines[i + 1:j], i)
out = []
for l in lines:
    m = re.match(r"^(\s*)(- |steps: )\*([\w-]+)\s*$", l)
    a = re.match(r"^(\s*)(- |steps: )&([\w-]+)\s*$", l)
    if a:
        out.append(f"{a.group(1)}{a.group(2).rstrip()}" + ("" if a.group(2) == "steps: " else "") + f"  # shared step '{a.group(3)}': keep copies in sync")
        if a.group(2) == "- ": out[-1] = f"{a.group(1)}# shared step '{a.group(3)}': keep copies in sync"; out.append(None)
        continue
    if m:
        kind, body, _ = blocks[m.group(3)]
        if kind == "steps: ":
            out.append(f"{m.group(1)}steps: # copy of '{m.group(3)}': keep in sync"); out += body
        else:
            out.append(f"{m.group(1)}# copy of shared step '{m.group(3)}': keep in sync")
            first = body[0]; out.append(first[:ind(l)] + "- " + first[ind(l) + 2:]); out += body[1:]
        continue
    out.append(l)
# a "- &x" anchor line is replaced by its comment, and its first body line gets the dash
res = []; dash_next = False
for l in out:
    if l is None: dash_next = True; continue
    if dash_next:
        k = ind(l) - 2; res.append(l[:k] + "- " + l[k + 2:]); dash_next = False
    else: res.append(l)
res = [re.sub(r"^(\s*(?:- )?uses: )\$/", r"\1./", l) for l in res]
open(p, "w").write("\n".join(res))
