"""TTS utilities — sentence splitting for streaming playback."""
import re

# Sentence boundary: . ! ? Hindi danda (।) and newlines
_SENTENCE_BOUNDARY = re.compile(r'(?<=[.!?।])\s+')

def split_sentences(text: str) -> list[str]:
    """Split text into sentences."""
    text = text.strip()
    if not text:
        return []
    parts = _SENTENCE_BOUNDARY.split(text)
    return [p.strip() for p in parts if p.strip()]


def pop_complete_sentences(buffer: str) -> tuple[list[str], str]:
    """
    Extract complete sentences from a streaming buffer.
    Returns (complete_sentences, remaining_partial_text).
    """
    sentences: list[str] = []
    remaining = buffer

    while remaining:
        # Find first sentence-ending punctuation followed by space or end
        match = re.search(r'[.!?।](?:\s|$)', remaining)
        if not match:
            break
        end = match.end()
        candidate = remaining[:end].strip()
        if len(candidate) >= 2:
            sentences.append(candidate)
            remaining = remaining[end:].lstrip()
        else:
            break

    return sentences, remaining
