from pathlib import Path

import pytest
from lxml import etree

from epg_archive.models import EPGSource
from epg_archive.orchestrator import EPGOrchestrator


@pytest.mark.asyncio
async def test_run_preserves_existing_programmes_and_channels(tmp_path: Path) -> None:
    archive_dir = tmp_path / "archive"
    day_dir = archive_dir / "2026"
    day_dir.mkdir(parents=True, exist_ok=True)
    day_file = day_dir / "2026-01-01.xml"

    day_file.write_text(
        """<?xml version='1.0' encoding='UTF-8'?>
<tv>
  <channel id="A.fr">
    <display-name>Channel A</display-name>
  </channel>
  <programme channel="A.fr" start="20260101090000 +0100" stop="20260101100000 +0100">
    <title lang="fr">Old Show</title>
  </programme>
</tv>
""",
        encoding="utf-8",
    )

    new_xml = b"""<?xml version='1.0' encoding='UTF-8'?>
<tv>
  <channel id="B.fr">
    <display-name>Channel B</display-name>
  </channel>
  <programme channel="B.fr" start="20260101100000 +0100" stop="20260101110000 +0100">
    <title lang="fr">New Show</title>
  </programme>
</tv>
"""

    source = EPGSource(
        name="TestSource",
        url="https://example.test/epg.xml",
        priority=1,
        enabled=True,
    )
    orchestrator = EPGOrchestrator([source], archive_dir)

    async def fake_fetch(_url: str) -> bytes:
        return new_xml

    orchestrator.fetcher.fetch = fake_fetch  # type: ignore[assignment]

    await orchestrator.run()

    tree = etree.parse(str(day_file))
    root = tree.getroot()

    channel_ids = {channel.get("id") for channel in root.findall("channel")}
    assert channel_ids == {"A.fr", "B.fr"}

    programme_keys = {
        (prog.get("channel"), prog.get("start"), prog.get("stop"))
        for prog in root.findall("programme")
    }
    assert ("A.fr", "20260101090000 +0100", "20260101100000 +0100") in programme_keys
    assert ("B.fr", "20260101100000 +0100", "20260101110000 +0100") in programme_keys
