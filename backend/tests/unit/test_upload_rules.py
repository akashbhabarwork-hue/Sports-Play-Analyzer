import pytest

from app.core.file_sniff import AVI, MATROSKA, MP4, sniff_video_container
from app.core.models import VideoProbe
from app.core.video_rules import check_video_limits
from app.errors import CorruptFileError, DurationExceededError


@pytest.mark.parametrize(
    ("head", "expected"),
    [
        (b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00", MP4),
        (b"\x00\x00\x00\x14ftypqt  \x00\x00\x00\x00", MP4),  # MOV
        (b"\x1a\x45\xdf\xa3\x9f\x42\x86\x81\x01\x42\xf7\x81", MATROSKA),  # MKV / WebM
        (b"RIFF\x00\x10\x00\x00AVI LIST", AVI),
        (b"RIFF\x00\x10\x00\x00WAVEfmt ", None),  # audio, not video
        (b"<html><body>hi</body>", None),
        (b"#!/bin/sh\nrm -rf /", None),
        (b"\x89PNG\r\n\x1a\n\x00\x00\x00\r", None),
        (b"ftyp", None),  # too short to be real
        (b"", None),
    ],
)
def test_upload_sniff_by_content(head, expected):
    assert sniff_video_container(head) is expected


def probe(duration=10.0, width=640, height=360) -> VideoProbe:
    return VideoProbe("mov,mp4", duration, width, height, 25.0)


def test_upload_rules_accept_a_normal_clip():
    check_video_limits(probe(), 60)
    check_video_limits(probe(duration=60.4), 60)  # container rounding tolerance


@pytest.mark.parametrize(
    ("p", "error"),
    [
        (probe(duration=61.0), DurationExceededError),
        (probe(duration=0), CorruptFileError),
        (probe(width=0), CorruptFileError),
        (probe(width=8000, height=4000), CorruptFileError),
    ],
)
def test_upload_rules_reject(p, error):
    with pytest.raises(error):
        check_video_limits(p, 60)
