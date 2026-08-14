# Agent operating rules

1. Narration and final voice audio are the master timeline.
2. Agents output data contracts, not final edit code, unless the task explicitly requires code/media.
3. Every structured result must validate against a Pydantic schema before the pipeline advances.
4. Every task declares a capability. Never route a task to an incompatible provider.
5. Prefer deterministic code for exact transformations; use AI for ambiguity, interpretation and creative planning.
6. Prototype demos use synthetic data only unless the operator explicitly supplies safe production data.
7. Director output is normalized by hard production budgets before asset generation.
8. Missing/failed visual assets fail soft to talking head or a deterministic graphic; never silently invent production claims.
9. HyperFrames is the primary deterministic renderer. FFmpeg is the concat/mux/fallback layer.
10. Final publishing always requires operator approval.
