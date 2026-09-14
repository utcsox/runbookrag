"""Chunk markdown runbooks into embeddable pieces.

Splits on headings rather than fixed-size windows, since a runbook's
meaning lives in its section structure (Symptoms / Diagnose / Mitigation).
Each chunk is prefixed with its heading breadcrumb so it stays meaningful
in isolation once embedded, and oversized sections are further split
without ever cutting inside a fenced code block.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_MAX_CHARS = 1500
DEFAULT_CHUNK_OVERLAP = 200

_HEADER_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_FENCE_RE = re.compile(r"^(```|~~~)")


def _fence_marker(line: str) -> str | None:
    """Return the fence marker if this line toggles fenced-block state.

    A line that opens and closes the fence on itself (e.g. `` ```cmd``` ``)
    doesn't change block state - it's inline content, not a block boundary.
    """
    stripped = line.strip()
    match = _FENCE_RE.match(stripped)
    if not match:
        return None
    marker = match.group(1)
    rest = stripped[len(marker) :]
    if rest.endswith(marker) and len(rest) > len(marker):
        return None
    return marker


@dataclass
class Chunk:
    text: str
    heading_path: list[str]
    source: str
    chunk_index: int


@dataclass
class _Section:
    heading: str
    parent_path: list[str] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)

    @property
    def heading_path(self) -> list[str]:
        return [*self.parent_path, self.heading] if self.heading else self.parent_path

    @property
    def body(self) -> str:
        return "\n".join(self.lines).strip()


def _split_into_sections(markdown: str) -> list[_Section]:
    sections: list[_Section] = []
    stack: list[str] = []
    current = _Section(heading="")
    in_fence = False

    for line in markdown.splitlines():
        if _fence_marker(line) is not None:
            in_fence = not in_fence
            current.lines.append(line)
            continue

        header_match = None if in_fence else _HEADER_RE.match(line)
        if header_match:
            if current.body:
                sections.append(current)
            level = len(header_match.group(1))
            heading = header_match.group(2).strip()
            del stack[level - 1 :]
            parent_path = list(stack)
            stack.append(heading)
            current = _Section(heading=heading, parent_path=parent_path)
        else:
            current.lines.append(line)

    if current.body:
        sections.append(current)

    return sections


def _trailing_overlap(buf: list[str], overlap_chars: int) -> list[str]:
    """Return a fence-safe suffix of buf to carry into the next piece.

    Scans backward accumulating lines, but only "commits" to a candidate
    suffix at points where no fence is left dangling open - so overlap
    never reproduces half of a code block.
    """
    if overlap_chars <= 0 or not buf:
        return []

    best: list[str] = []
    included: list[str] = []
    included_len = 0
    fence_open = False

    for line in reversed(buf):
        if _fence_marker(line) is not None:
            fence_open = not fence_open
        included.insert(0, line)
        included_len += len(line) + 1
        if included_len > overlap_chars:
            break
        if not fence_open:
            best = list(included)

    return best


def _split_body(body: str, max_chars: int, overlap_chars: int = 0) -> list[str]:
    if len(body) <= max_chars:
        return [body]

    parts: list[str] = []
    buf: list[str] = []
    buf_len = 0
    in_fence = False

    for line in body.splitlines():
        is_fence_marker = _fence_marker(line) is not None
        was_in_fence = in_fence
        if is_fence_marker:
            in_fence = not in_fence
        line_in_fence_block = was_in_fence or is_fence_marker

        line_len = len(line) + 1
        if not line_in_fence_block and buf and buf_len + line_len > max_chars:
            parts.append("\n".join(buf).strip())
            buf = _trailing_overlap(buf, overlap_chars)
            buf_len = sum(len(carried) + 1 for carried in buf)
        buf.append(line)
        buf_len += line_len

    if buf:
        parts.append("\n".join(buf).strip())

    return [part for part in parts if part]


def chunk_markdown(
    markdown: str,
    source: str,
    max_chars: int = DEFAULT_MAX_CHARS,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Chunk]:
    if chunk_overlap >= max_chars:
        raise ValueError(
            f"chunk_overlap ({chunk_overlap}) must be smaller than "
            f"max_chars ({max_chars})"
        )

    chunks: list[Chunk] = []
    for section in _split_into_sections(markdown):
        breadcrumb = " > ".join(section.heading_path)
        for piece in _split_body(section.body, max_chars, chunk_overlap):
            text = f"{breadcrumb}\n\n{piece}" if breadcrumb else piece
            chunks.append(
                Chunk(
                    text=text,
                    heading_path=section.heading_path,
                    source=source,
                    chunk_index=len(chunks),
                )
            )
    return chunks


def chunk_file(
    path: Path,
    max_chars: int = DEFAULT_MAX_CHARS,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[Chunk]:
    return chunk_markdown(
        path.read_text(), source=str(path), max_chars=max_chars, chunk_overlap=chunk_overlap
    )
