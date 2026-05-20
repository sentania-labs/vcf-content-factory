# Decision Overrides

This directory contains explicit relitigation artifacts for previously decided matters.

## When to create an override

Only when:
1. New evidence directly contradicts the original decision basis
2. The target API changed in a way that invalidates a trigger
3. Framework capabilities expanded to handle a previously impossible case

## Override ceremony

To override a decision:

1. Create `DEC-NNN-override.md` in this directory
2. Document which evidence changed since the original decision
3. Reference new findings (cleanroom spec, API discovery, framework capability)
4. The override must be approved by the framework maintainer

## Who can override

Casual users cannot relitigate. This directory is the expert gate.

Framework maintainers only.
