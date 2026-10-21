"""Recognize English text from image bytes with Windows OCR."""

from __future__ import annotations

import asyncio

from winrt.windows.globalization import Language
from winrt.windows.graphics.imaging import BitmapDecoder
from winrt.windows.media.ocr import OcrEngine
from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream


class OcrUnavailableError(RuntimeError):
    """The English Windows OCR language pack is not available."""


async def _recognize_png(png_bytes: bytes) -> str:
    engine = OcrEngine.try_create_from_language(Language("en-US"))
    if engine is None:
        raise OcrUnavailableError("English (en-US) OCR is unavailable in Windows settings.")

    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream.get_output_stream_at(0))
    try:
        writer.write_bytes(png_bytes)
        await writer.store_async()
        await writer.flush_async()
        stream.seek(0)
        decoder = await BitmapDecoder.create_async(stream)
        bitmap = await decoder.get_software_bitmap_async()
        result = await engine.recognize_async(bitmap)
        return "\n".join(line.text.strip() for line in result.lines if line.text.strip()).strip()
    finally:
        writer.close()
        stream.close()


def recognize_png(png_bytes: bytes) -> str:
    """Run WinRT OCR on a worker thread so the Qt interface stays responsive."""
    if not png_bytes:
        return ""
    return asyncio.run(_recognize_png(png_bytes))
