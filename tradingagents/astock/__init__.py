"""A-share capability catalog and implementation blueprint.

This package turns the screenshot requirements into a structured, reusable
specification that can drive future data-source, UI, and execution work.
"""

from .blueprint import (
    ASTOCK_BLUEPRINT,
    build_blueprint_markdown,
    build_blueprint_payload,
)

__all__ = [
    "ASTOCK_BLUEPRINT",
    "build_blueprint_markdown",
    "build_blueprint_payload",
]
