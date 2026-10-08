"""
compression.py — API Response Compression
Implements gzip compression for API responses.
"""

from logger_setup import get_logger
logger = get_logger(__name__)

import gzip
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.datastructures import Headers


class GZipMiddleware(BaseHTTPMiddleware):
    """
    Middleware to compress API responses with gzip.
    Only compresses responses larger than 1KB.
    """
    
    def __init__(self, app, minimum_size=1024, compression_level=6):
        super().__init__(app)
        self.minimum_size = minimum_size
        self.compression_level = compression_level
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        
        # Check if client accepts gzip
        accept_encoding = request.headers.get("accept-encoding", "")
        if "gzip" not in accept_encoding.lower():
            return response
        
        # Don't compress if response is already compressed
        if response.headers.get("content-encoding"):
            return response
        
        # Don't compress images, videos, or already compressed formats
        content_type = response.headers.get("content-type", "")
        excluded_types = ["image/", "video/", "audio/", "application/zip", "application/gzip"]
        if any(ct in content_type for ct in excluded_types):
            return response
        
        # Get response body
        response_body = b""
        async for chunk in response.body_iterator:
            response_body += chunk
        
        # Only compress if body is larger than minimum_size
        if len(response_body) < self.minimum_size:
            return Response(
                content=response_body,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=response.media_type
            )
        
        # Compress with gzip
        compressed_body = gzip.compress(response_body, compresslevel=self.compression_level)
        
        # Calculate compression ratio
        ratio = (1 - len(compressed_body) / len(response_body)) * 100
        logger.debug(f"[COMPRESSION] {len(response_body)} → {len(compressed_body)} bytes ({ratio:.1f}% saved)")
        
        # Build new headers
        headers = dict(response.headers)
        headers["content-encoding"] = "gzip"
        headers["content-length"] = str(len(compressed_body))
        
        return Response(
            content=compressed_body,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type
        )
