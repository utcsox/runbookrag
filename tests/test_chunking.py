from pathlib import Path

from app.ingestion.chunking import chunk_file, chunk_markdown

RUNBOOKS_DIR = Path(__file__).parent.parent / "data" / "runbooks" / "gitlab"


def test_splits_on_headings_with_breadcrumb():
    markdown = """# Gitaly is down

## Symptoms

Alert fired.

## Diagnose

Check the logs.
"""
    chunks = chunk_markdown(markdown, source="test.md")

    assert [c.heading_path for c in chunks] == [
        ["Gitaly is down", "Symptoms"],
        ["Gitaly is down", "Diagnose"],
    ]
    assert chunks[0].text.startswith("Gitaly is down > Symptoms\n\n")


def test_never_splits_inside_a_fenced_code_block():
    body_lines = "\n".join(f"line {i}" for i in range(200))
    markdown = f"""# Runbook

## Big block

```
{body_lines}
```
"""
    chunks = chunk_markdown(markdown, source="test.md", max_chars=100, chunk_overlap=0)

    assert len(chunks) == 1
    assert chunks[0].text.count("```") == 2


def test_self_closing_fence_on_one_line_does_not_toggle_state():
    markdown = """# Runbook

## Step

Run `cmd` inline: ```sudo iotop -P -a```

Then a real block:

```
echo hello
```
"""
    chunks = chunk_markdown(markdown, source="test.md")

    assert len(chunks) == 1
    assert chunks[0].text.count("```") == 4


def test_overlap_carries_trailing_lines_into_next_piece():
    paragraphs = [f"paragraph {i} " + ("x" * 20) for i in range(10)]
    markdown = "# Runbook\n\n## Section\n\n" + "\n\n".join(paragraphs) + "\n"

    chunks = chunk_markdown(markdown, source="test.md", max_chars=100, chunk_overlap=40)

    assert len(chunks) > 1
    first_tail = chunks[0].text.strip().splitlines()[-1]
    assert first_tail in chunks[1].text


def test_overlap_never_splits_a_carried_fence():
    body_lines = "\n".join(f"line {i}" for i in range(200))
    markdown = f"""# Runbook

## Big block

Some intro text before the code.

```
{body_lines}
```

More text after the code.
"""
    chunks = chunk_markdown(markdown, source="test.md", max_chars=200, chunk_overlap=50)

    for chunk in chunks:
        assert chunk.text.count("```") % 2 == 0


def test_chunk_overlap_must_be_smaller_than_max_chars():
    try:
        chunk_markdown("# Runbook\n\nbody", source="test.md", max_chars=100, chunk_overlap=100)
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for chunk_overlap >= max_chars")


def test_real_runbooks_chunk_without_error():
    paths = list(RUNBOOKS_DIR.glob("*.md"))
    assert paths, "expected sample runbooks in data/runbooks/gitlab"

    for path in paths:
        chunks = chunk_file(path)
        assert chunks, f"no chunks produced for {path.name}"
        for chunk in chunks:
            assert chunk.text.strip()
            assert chunk.source == str(path.resolve())


def test_chunk_file_source_is_stable_across_relative_and_absolute_paths(monkeypatch):
    monkeypatch.chdir(RUNBOOKS_DIR.parent.parent.parent)
    relative_path = Path("data/runbooks/gitlab/gitaly-down.md")
    absolute_path = relative_path.resolve()

    from_relative = chunk_file(relative_path)
    from_absolute = chunk_file(absolute_path)

    assert from_relative[0].source == from_absolute[0].source == str(absolute_path)
