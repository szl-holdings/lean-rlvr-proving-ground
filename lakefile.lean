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
