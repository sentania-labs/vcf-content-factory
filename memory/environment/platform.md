# Platform context

Per-deployment state. Not part of the framework soul — specific to this instance.

## Lab instances

- devel — MPB pipeline canonical
- prod — factory pipeline canonical

## Versions

- VCF Operations version tested against: 9.0.2

## Known capability gaps

- MPB: no JMESPath filter projections (targeting 9.2)
- `isUnremovable` flag not enforced server-side (see lessons/)
