"""Identify a video container from its first bytes (pure). Extension and Content-Type are
client-controlled and never trusted."""

from dataclasses import dataclass

SNIFF_BYTES = 16


@dataclass(frozen=True, slots=True)
class Container:
    name: str
    extension: str  # used for the blob key
    content_type: str


MP4 = Container("mp4", "mp4", "video/mp4")  # MP4 / MOV / M4V / 3GP (ISO BMFF)
MATROSKA = Container("matroska", "mkv", "video/x-matroska")  # MKV / WebM
AVI = Container("avi", "avi", "video/x-msvideo")


def sniff_video_container(head: bytes) -> Container | None:
    if len(head) >= 12 and head[4:8] == b"ftyp":
        return MP4
    if head[:4] == b"\x1a\x45\xdf\xa3":
        return MATROSKA
    if len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"AVI ":
        return AVI
    return None
