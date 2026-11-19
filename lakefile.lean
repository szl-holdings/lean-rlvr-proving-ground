import Lake
open Lake DSL

package leanrlvr where
  -- SZL proving-ground RLVR referee sandbox (core-only, NO Mathlib
  -- dependency) so kernel checks run cold in seconds on any node.
  -- Toolchain pinned to lutar-lean v4.35.0 (the kernel referee's
  -- acceptance toolchain).

@[default_target]
lean_lib Probes where
  srcDir := "probes"

-- Independent core-only, limited historical arithmetic witnesses. Do not
-- append these to Lutar's locked theorem list or make GPU/model claims.
@[default_target]
lean_lib Proving54 where
  srcDir := "probes"
  roots := #[`Proving54]

-- Research-only support algebra (SZL.BoundaryResearch). Core Lean, no Mathlib.
-- Previously never built by `lake build`; now kernel-checked by default.
@[default_target]
lean_lib SupportBoundary where
  srcDir := "research/boundary_lab"
  roots := #[`SupportBoundary]
