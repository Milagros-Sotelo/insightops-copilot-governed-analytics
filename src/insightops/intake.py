"""Safe multi-format file intake and metadata inspection."""

from __future__ import annotations

import csv
import hashlib
import io
from pathlib import Path
from typing import BinaryIO

import pandas as pd

from .models import SourceFile


SUPPORTED_EXTENSIONS = {".csv", ".xlsx"}


def file_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def detect_encoding(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            data.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    return "latin-1"


def detect_separator(data: bytes, encoding: str) -> str:
    sample = data[:8192].decode(encoding, errors="replace")
    try:
        return csv.Sniffer().sniff(sample, delimiters=",;\t|").delimiter
    except csv.Error:
        counts = {separator: sample.count(separator) for separator in (",", ";", "\t", "|")}
        return max(counts, key=counts.get)


class IntakeRegistry:
    def __init__(self, max_file_mb: int = 25) -> None:
        self.max_bytes = max_file_mb * 1024 * 1024
        self._hashes: dict[str, str] = {}

    def inspect(self, file_name: str, data: bytes, user: str = "demo.user@asteria.example") -> SourceFile:
        suffix = Path(file_name).suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"Unsupported file type: {suffix}")
        if len(data) == 0:
            raise ValueError("Empty files are not accepted")
        if len(data) > self.max_bytes:
            raise ValueError(f"File exceeds the {self.max_bytes // (1024 * 1024)} MB limit")
        digest = file_hash(data)
        duplicate = self._hashes.get(digest)
        encoding, separator, sheets = "binary", "", ()
        if suffix == ".csv":
            encoding = detect_encoding(data)
            separator = detect_separator(data, encoding)
        else:
            sheets = tuple(pd.ExcelFile(io.BytesIO(data)).sheet_names)
        metadata = SourceFile(
            file_name=file_name, file_hash=digest, size_bytes=len(data),
            encoding=encoding, separator=separator, sheet_names=sheets,
            uploaded_by=user, status="duplicate" if duplicate else "received",
            duplicate_of=duplicate,
        )
        self._hashes.setdefault(digest, file_name)
        return metadata

    def read(self, file_name: str, data: bytes, sheet_name: str | int = 0) -> tuple[SourceFile, pd.DataFrame]:
        metadata = self.inspect(file_name, data)
        if Path(file_name).suffix.lower() == ".csv":
            frame = pd.read_csv(io.BytesIO(data), encoding=metadata.encoding, sep=metadata.separator)
        else:
            frame = pd.read_excel(io.BytesIO(data), sheet_name=sheet_name)
        return metadata, frame

    def read_path(self, path: str | Path, user: str = "demo.user@asteria.example") -> tuple[SourceFile, pd.DataFrame]:
        source = Path(path)
        data = source.read_bytes()
        metadata = self.inspect(source.name, data, user=user)
        if source.suffix.lower() == ".csv":
            frame = pd.read_csv(io.BytesIO(data), encoding=metadata.encoding, sep=metadata.separator)
        else:
            frame = pd.read_excel(io.BytesIO(data), sheet_name=0)
        return metadata, frame

