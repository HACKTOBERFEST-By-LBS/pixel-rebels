**Source visual truth**
- Dashboard references supplied by the user: `cosmos_793713085.webp`, `2f1a23dc-696b-4a75-8951-728142c36611.webp`, and `cosmos_1006637506.webp`.

**Implementation state**
- Next.js App Router migration in the current workspace.
- Intended viewport: desktop dashboard, 1440 px wide.
- Intended primary interactions: scanner message input, attachment selection, `/apprendre` actions, chat history and help modal.

**Verification status**
- Browser-rendered Next.js screenshot: unavailable. Dependency installation did not finish because npm registry downloads timed out on this host.
- The existing browser tab still serves the former local FastAPI process and is not evidence for the new Next.js build.

**Findings**
- [P0] The new Next.js build could not be launched locally because the package manager was blocked while retrieving the Windows SWC binary.
  Impact: the new dashboard cannot be visually compared or interaction-tested in this environment.
  Fix: run `pnpm install` from a normal network connection, then `pnpm build` and `pnpm dev`.

**Final result**
blocked
