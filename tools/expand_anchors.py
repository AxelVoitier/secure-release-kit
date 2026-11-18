# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
"""Expand shared workflow steps in a local copy for act and actionlint."""

import argparse
import re
from pathlib import Path

# The kit shares individual list items and entire steps lists. In both cases
# the definition and its references have the same indentation.
SHARED_STEPS = re.compile(r'^( *)(- |steps: )([&*])([\w-]+)\s*$')
SELF_CALL = re.compile(r'^(\s*(?:- )?uses: )\$/')


def expand_workflow(source: str) -> str:
    lines = source.split('\n')
    anchors: dict[str, list[str]] = {}
    result: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        match = SHARED_STEPS.fullmatch(line)
        if match is None:
            result.append(line)
            continue

        indent, kind, marker, name = match.groups()
        if marker == '&':
            start = index
            while index < len(lines):
                child = lines[index]
                if child.strip() and not child.startswith(indent + ' '):
                    break
                index += 1
            while index > start and not lines[index - 1].strip():
                index -= 1
            body = lines[start:index]
            if kind == '- ':
                # Move the sequence marker to the first key of the shared step.
                body[0] = indent + '- ' + body[0][len(indent) + 2 :]
            anchors[name] = body
        label = 'shared' if marker == '&' else 'copy of shared'
        result.append(f'{indent}# {label} step {name!r}: keep copies in sync')
        if kind == 'steps: ':
            result.append(indent + 'steps:')
        result.extend(anchors[name])

    return '\n'.join(SELF_CALL.sub(r'\1./', line) for line in result)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('workflow', type=Path, help='workflow copy to rewrite in place')
    path: Path = parser.parse_args().workflow
    path.write_text(expand_workflow(path.read_text()))


if __name__ == '__main__':
    main()
