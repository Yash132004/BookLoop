"""Small, local helpers for creating and comparing book text embeddings."""

import logging
from functools import lru_cache
from math import sqrt

logger = logging.getLogger(__name__)


def book_search_text(book):
    """Combine the listing's real text fields into one searchable document."""
    return ' '.join(filter(None, (
        book.title,
        book.author,
        book.description,
        book.get_condition_display(),
        book.location,
    )))


@lru_cache(maxsize=1)
def _embedding_model():
    # The model and ONNX runtime load only when a listing is indexed or a
    # non-empty search is submitted. Django startup does not load the ML stack.
    from fastembed import TextEmbedding

    return TextEmbedding(model_name='sentence-transformers/all-MiniLM-L6-v2')


def embed_text(text):
    """Return a locally generated vector, or None if FastEmbed is unavailable."""
    if not text or not text.strip():
        return None

    try:
        vector = next(_embedding_model().embed([text]))
        return vector.tolist()
    except ImportError:
        logger.warning('FastEmbed is not installed; using title/author search only.')
    except Exception:
        # Model downloads and runtime initialization should not prevent the
        # marketplace from loading or a seller from saving a listing.
        logger.exception('Semantic embedding was unavailable; using keyword search.')
    return None


def cosine_similarity(first, second):
    """Return cosine similarity for two stored vectors, or zero if absent."""
    if not first or not second or len(first) != len(second):
        return 0.0

    dot_product = sum(left * right for left, right in zip(first, second))
    first_length = sqrt(sum(value * value for value in first))
    second_length = sqrt(sum(value * value for value in second))
    if not first_length or not second_length:
        return 0.0
    return dot_product / (first_length * second_length)
