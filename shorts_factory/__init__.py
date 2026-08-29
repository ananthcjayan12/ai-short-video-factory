__version__ = "0.3.0-whiteboard"

from .editorial_orchestrator import register_editorial_tasks

register_editorial_tasks()

del register_editorial_tasks

from .editorial_v3_schema import install_v3_provider_schema

install_v3_provider_schema()

del install_v3_provider_schema
