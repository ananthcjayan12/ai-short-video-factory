"""Local production desk for the short-video factory.

Factory Desk historically imports ``generate_graphics_plan`` from ``pipeline``.
Route that legacy import to the V3 editorial implementation before ``ui.server``
is loaded so the web UI and CLI cannot accidentally use different graphics
planners.
"""

from .. import pipeline as _pipeline
from ..editorial_v3 import generate_graphics_plan as _generate_graphics_plan

_pipeline.generate_graphics_plan = _generate_graphics_plan

del _generate_graphics_plan
del _pipeline
