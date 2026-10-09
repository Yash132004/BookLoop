"""Local image-vector helpers for BookListing cover search."""

from functools import lru_cache
import logging

from PIL import Image, ImageOps

logger = logging.getLogger(__name__)
IMAGE_MODEL_NAME = 'Qdrant/clip-ViT-B-32-vision'


@lru_cache(maxsize=1)
def _image_embedding_model():
    """Load the vision model only when an image is indexed or searched."""
    from fastembed import ImageEmbedding

    return ImageEmbedding(model_name=IMAGE_MODEL_NAME)


def embed_image(image_source):
    """Return a Python list containing one image's visual embedding."""
    embeddings = _image_embedding_model().embed([image_source])
    return next(embeddings).tolist()


def embed_uploaded_image(uploaded_file):
    """Embed a validated upload in memory without saving it to media storage."""
    uploaded_file.seek(0)
    with Image.open(uploaded_file) as image:
        image = ImageOps.exif_transpose(image).convert('RGB')
        embedding = embed_image(image)
    uploaded_file.seek(0)
    return embedding


def embed_listing_image(book):
    """Create an embedding from a listing's saved image, or an empty vector."""
    if not book.image:
        return []

    try:
        return embed_image(book.image.path)
    except Exception:
        logger.exception('Could not generate image embedding for listing %s.', book.pk)
        return []
