__version__ = "0.2.0-sketch"

from .editorial_orchestrator import register_editorial_tasks

register_editorial_tasks()

del register_editorial_tasks

from .editorial_v3_schema import install_v3_provider_schema

install_v3_provider_schema()

del install_v3_provider_schema

# This branch replaces the HTML/CSS/JavaScript graphics compiler with a
# Director-approved image + image-to-video sketch pipeline while preserving the
# existing Factory Desk, orchestration, Director, prototype, recording and
# composition code paths. Patch both public entry points so CLI and UI use the
# same implementation without duplicating the rest of the production system.
from . import editorial_v3 as _editorial_v3
from . import pipeline as _pipeline
from .sketch_graphics import generate_sketch_graphics_plan as _generate_sketch_graphics_plan

_pipeline.generate_graphics_plan = _generate_sketch_graphics_plan
_editorial_v3.generate_graphics_plan = _generate_sketch_graphics_plan

del _generate_sketch_graphics_plan
