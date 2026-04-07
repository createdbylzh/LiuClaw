"""`ai.utils` 提供统一接入层可复用的通用基础设施。"""

from .context_window import (
    ContextOverflowError,
    ContextOverflowReport,
    detect_context_overflow,
    ensure_context_fits_window,
    estimate_context_tokens,
)
from .schema_validation import SchemaValidationError, validate_tool_arguments
from .streaming import EventBuilder, StreamAccumulator, create_done_event
from .unicode import sanitize_unicode, sanitize_unicode_context

__all__ = [
    "ContextOverflowError",
    "ContextOverflowReport",
    "EventBuilder",
    "SchemaValidationError",
    "StreamAccumulator",
    "create_done_event",
    "detect_context_overflow",
    "ensure_context_fits_window",
    "estimate_context_tokens",
    "sanitize_unicode",
    "sanitize_unicode_context",
    "validate_tool_arguments",
]
