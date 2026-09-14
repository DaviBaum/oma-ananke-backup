# Shared physical distribution networks

The workbench's shared-network mission checks one physical component tree against an imported building. A trunk or tee used by two demands is authored, displayed and charged once. Each demand retains its own fixed sink, section, flow and pressure requirement.

The present family supports one source, at least two sinks, equal circular sections, straight segments, circular elbows and orthogonal three-port tees. Every connection and oriented demand path is explicit. The schema rejects duplicated components, disconnected branches, cycles, unused ports, inconsistent flow directions, changes to fixed terminals or sections, and undersized fitting takeouts. Each complete alternative is materialized in a copy of the original IFC. An independently checked finite co-design selection compares the actual feasible alternatives; no unrestricted continuous or topology optimum follows.

An initial network mission requires a baseline with no previous engineered mission. Operations that would silently discard an existing route or network are blocked. Network-preserving edits, reducers, arbitrary fittings, multiple supplies, loops, drainage collection and original equipment-port attachment are still open capabilities.

`network_checker.py` reloads the immutable request, candidate and source hashes, checks exact obligation coverage and source preservation, then reads actual native IFC geometry, ports, component connectivity and system membership. It checks every component against all imported source obstacles, every component pair and each full solid against the permitted zone. Native and analytic volumes and path lengths cross-check each other. Numerical CAD tolerances and source-envelope policies are explicit evidence assumptions.

A bounded early phase may reject a candidate using one fresh native positive-common-volume witness. Proposal boxes only choose work. No witness, a timeout or unsupported geometry sends the candidate through the ordinary full checker. On early rejection, every remaining denominator and service check is recorded as `NOT_RUN`; this phase cannot accept a candidate.

The optional service calculation sums fixed downstream flows on each shared component and checks every port's velocity. Each demand's static pressure requirement includes straight and curved-pipe Darcy losses, explicit elbow and tee loss conventions, elevation and kinetic-head differences. Tee losses use the inlet velocity and include the whole tee's irreversible local loss; the tee skeleton is not charged a second Darcy loss. Exact rational intervals propagate the declared numerical metric budget. The result is conditional on supplied fluid properties, loss applicability and external flow controls. A hydraulic operating point is `NOT_ESTABLISHED`.

Checked export copies the full replacement and every unchanged discipline, rereads the exported network, and runs a fresh complete check with export correspondence. Backup/relocation tests recheck actual restored IFC bytes with the original store unavailable and preserve the same content root.

## Real Office benchmark

The frozen scenario in `evidence/benchmarks/shared-network/office/b36e301376fe49ed90a2525e51f69275/` compares two supplied layouts with identical source/sinks, 100 mm internal diameter, 20 mm insulation, 100 mm clearance, fixed 1 and 2 L/s sink flows, and a 1,000 Pa pressure budget per demand. These are scenario inputs, not measured operating conditions or manufacturer ratings.

| Layout | Unique physical length | Fittings | Native components |
| --- | ---: | ---: | ---: |
| Offset tee | 1.981327412 m | 3 | 8 |
| Direct tee | 1.800000000 m | 1 | 4 |

Both alternatives passed their complete native and source checks. The direct layout saves 0.181327412 m within this two-alternative comparison. Its two demand paths are 1.2 m each; summing them would incorrectly charge the shared trunk twice. This is a new shared-source mission and is not comparable to the earlier Office mission with two independent sources.

The selected candidate `123924e355164a5ba330e5b30cc72384` was accepted in project `a561fdf78fcc411295e4821cb560c829`. Export `2089437ddc994677b46231ddb03a5b5d` passed fresh round-trip verification; the IFC SHA256 is `c116e3cf909e97719a613888043ca2b214aba538575e17f79dd3639bb5a12e58`. The complete run took 83.026 seconds at the executable version recorded in the result. Subsequent executable changes require renewed report applicability; historical evidence is retained.
