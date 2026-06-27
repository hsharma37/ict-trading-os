"""
Document processing utilities for the knowledge base.

Handles text chunking, cleaning, and preparation for embedding.
"""
import re
from typing import List, Dict, Any


def clean_text(text: str) -> str:
    """
    Clean and normalize text for embedding.
    """
    # Remove excessive whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove timestamps like [00:00:00] or (00:00)
    text = re.sub(r'\[\d{2}:\d{2}:\d{2}\]', '', text)
    text = re.sub(r'\(\d{2}:\d{2}\)', '', text)
    # Remove common YouTube metadata patterns
    text = re.sub(r'\d+ views?\s*\d+\s*(?:day|week|month|year)s?\s*ago', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\d+:\d+\s*$', '', text)  # Remove trailing timestamps
    # Strip and normalize
    text = text.strip()
    return text


def chunk_text(
    text: str,
    chunk_size: int = 512,
    chunk_overlap: int = 50,
    separator: str = "\n",
) -> List[str]:
    """
    Split text into overlapping chunks.

    Args:
        text: The text to chunk
        chunk_size: Target size of each chunk in characters (approximate)
        chunk_overlap: Number of characters to overlap between chunks
        separator: Preferred separator for splitting

    Returns:
        List of text chunks
    """
    if not text:
        return []

    # Split by separator first
    parts = text.split(separator)

    chunks = []
    current_chunk = []
    current_size = 0

    for part in parts:
        part = part.strip()
        if not part:
            continue

        part_size = len(part)

        if current_size + part_size > chunk_size and current_chunk:
            # Save current chunk
            chunks.append(separator.join(current_chunk))
            # Start new chunk with overlap
            overlap_chars = 0
            overlap_parts = []
            for prev_part in reversed(current_chunk):
                if overlap_chars + len(prev_part) <= chunk_overlap:
                    overlap_parts.insert(0, prev_part)
                    overlap_chars += len(prev_part) + len(separator)
                else:
                    break
            current_chunk = overlap_parts + [part]
            current_size = sum(len(p) for p in current_chunk) + len(separator) * (len(current_chunk) - 1)
        else:
            current_chunk.append(part)
            current_size += part_size + len(separator)

    # Add remaining chunk
    if current_chunk:
        chunks.append(separator.join(current_chunk))

    return chunks


def chunk_text_semantic(
    text: str,
    max_chunk_size: int = 512,
    chunk_overlap: int = 50,
) -> List[Dict[str, Any]]:
    """
    Create semantic chunks with metadata.

    Returns chunks with index, content, and word count.
    """
    chunks = chunk_text(text, chunk_size=max_chunk_size, chunk_overlap=chunk_overlap)

    result = []
    for i, chunk in enumerate(chunks):
        result.append({
            "chunk_index": i,
            "content": chunk,
            "word_count": len(chunk.split()),
            "char_count": len(chunk),
        })

    return result


def extract_youtube_id(url: str) -> str:
    """
    Extract YouTube video ID from URL.
    """
    patterns = [
        r'(?:youtube\.com\/watch\?v=|youtu\.be\/|youtube\.com\/embed\/)([^&\s?]+)',
        r'youtube\.com\/watch\?.*v=([^&\s]+)',
    ]

    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)

    return ""


def format_transcript_for_kb(raw_transcript: str, title: str = "") -> str:
    """
    Format a raw transcript for knowledge base storage.
    """
    cleaned = clean_text(raw_transcript)

    # Add title header if provided
    if title:
        cleaned = f"# {title}\n\n{cleaned}"

    return cleaned
