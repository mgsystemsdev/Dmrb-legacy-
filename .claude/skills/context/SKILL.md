---
name: context
description: >
  Fetch up-to-date docs for libraries, APIs, and frameworks.
  Use before writing code or when unsure about syntax or versions.
allowed-tools: Read, Grep, Glob, Bash, WebFetch, WebSearch
---

# Mission

Pull real, current documentation. Avoid stale knowledge.

# When to Use

- Before coding against APIs
- When debugging unknown behavior
- When version-specific logic matters

# Output

For orchestrator v2 JSON, include top-level `docs_used: string[]` (paths or URLs you relied on).

Otherwise:

- Relevant docs (with links or paths)
- Key snippets
- Version notes
