# Pair reuse: applicability and truth are separate obligations

This is a design review of `oma.ifc.cad.check_pair` and `cad_cache`, not an implemented pair-verdict cache. The current checker recomputes native pair operations. Its native geometry cache revalidates topology and independently rebuilds source enclosure certificates. It does not currently cache pair verdicts.

An exact input fingerprint can establish that a previous computation addresses the same pair. It cannot establish that an arbitrary persisted answer was computed correctly. A nearest-point pair proves an upper bound on distance; it cannot prove a lower distance bound, absence of interior overlap, or global separation. The stored zero common-volume number is likewise not an independently replayable proof of a Boolean operation.

## A narrow certificate that can be checked independently

Let the complete represented occupied supports be covered by finite cells, `A subset union_i A_i` and `B subset union_j B_j`. For each cell pair, supply a nonzero rational vector `n`, a checked upper bound `u >= sup_{x in A_i} n.x`, and a checked lower bound `l <= inf_{y in B_j} n.y`. For rational required separation `d >= 0`, the two exact inequalities

```
l - u > 0
(l - u)^2 > d^2 * (n.n)
```

imply every point pair is more than `d` apart. Every occupied-support cell pair must be covered. Source support completeness, placements, units, component interpretation and requested clearance remain separate checked inputs. A hole in the cell cover invalidates the certificate. A failed separating-plane test does not prove collision.

Rational boxes and source vertex hulls have exact support bounds: choose endpoints or vertices according to the sign of each coordinate. Existing exact source extraction can certify supported raw IFC cells; numerical native BRep bounds retain their explicitly declared numerical enclosure assumption. A formal source certificate must not silently inherit native numerical soundness. Curved route bodies need their own exact or outward interval support bounds, including fitting sweeps and insulation. The existing global AABB broad phase is already a cheap special case of this construction.

The checker may accept an untrusted proposed plane only after independently deriving the complete cell supports from current immutable inputs and verifying these inequalities. Neither a previous PASS flag nor a cache digest is authority. Unsupported cells or unsuccessful separation go to the current cold native checker and retain UNKNOWN/BLOCKED when it cannot decide. Authorized contact requires its full interface proof; it is outside this separation-certificate contract.

## Reusing a numerical native execution under an explicit trust contract

There is a different, conditional design: retain a trusted execution attestation for the exact original native pair operation and reuse it only after establishing complete input identity. That introduces the prior producer and attestation authenticity into the trusted computing base. It is not independent proof replay. An untrusted cache may locate an attestation but cannot author it. A hash and a mutable neighboring hash file are integrity checks, not an authenticity foundation.

The applicability key would have to bind both complete native shape serializations after placement, orientation/location/topology tolerances, source support and completeness dispositions, representation policy, all binary64 clearance/tolerance inputs, exact numerical budget convention, kernel/library/Python/build identities, and operation parameters such as Boolean fuzzy tolerance and parallel mode. Participant ordering must be preserved or explicitly normalized together with witness orientation. Labels are rebound only after the current identity mapping is checked. Contact authorization and later mission aggregation are separately checked and cannot be inherited from this pair key.

Native validity, matching volume and matching global bounds do not establish equality to the original source geometry. In particular, another solid can have the same volume and global bounds. Current cache loading uses those checks to detect corruption; it must retain its assumption that the immutable cached BRep was originally produced by the declared source conversion. A stronger hostile-cache model requires an authenticated conversion artifact or a fresh independent conversion/geometry-equivalence proof.

## Required comparison and likely benefit

Every current route/obstacle and component/component pair remains in the complete denominator. Record fresh, replay-checked, and cold-fallback dispositions separately. Compare a cache-enabled run to a cache-disabled run on the same immutable sources and executable build, including statuses, numerical results where deterministic, coordinate and support scope, missing objects and pair accounting. Test changed clearance, transforms, support policy, topology, source bytes, component geometry, contact metadata and altered cached witnesses. Never transform UNKNOWN into PASS through reuse.

Broad-phase replay is cheap already. Fine support cells may avoid expensive native calls for curved or nonconvex geometry whose global boxes overlap, but benefit is not established by this review. Profile native loading, transforms and actual narrow pair time separately before implementation. Full Digital Hub measurements so far have substantial source conversion, source enclosure and transform costs; a pair cache would not remove those gates.

Source trace: original P11 assumption/support authenticity and applicability obligations; integration CMP dependency-completeness and cold-equivalence obligations; RTR enclosure and full obstacle-denominator obligations. This contract corrects no original geometry claim by assumption. It defines two different explicit trust models and only the first provides independently checkable separation evidence.
