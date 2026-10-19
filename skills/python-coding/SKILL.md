---
name: python-coding
description: Personal Python coding conventions. Use when writing or editing a .py file for this user.
---

## Variable naming: type-prefix convention

Python has no static typing, so prefix variable names with a short prefix indicating their structure:
- `d_` — dict
- `a_` — numpy array
- `s_` — set, or pandas Series
- `df_` — pandas DataFrame
- `l_` — list

Scalars (int, float, str, bool) get no prefix.

## Code shape: concise over decomposed

Prefer short, concise Python over splitting logic into many functions for the sake of hypothetical reusability. Nesting functions (defining a helper inside the function that uses it) is fine and often preferred over flattening everything to one layer — the goal in both cases is to make it easy to trace who calls what; many same-level functions make that harder to follow, not easier.

Comment more liberally than usual to compensate for the terser code and shallower function decomposition — this overrides the general "don't add comments" default for Python specifically.
