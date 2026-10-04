"""
Importing this package registers every available connector with
`app.connectors.registry` (each connector module's `@register(...)`
decorator only runs once its module is imported). Add new connector
modules to this list as they're added.
"""
from app.connectors.gem import connector as _gem_connector  # noqa: F401

__all__: list[str] = []
