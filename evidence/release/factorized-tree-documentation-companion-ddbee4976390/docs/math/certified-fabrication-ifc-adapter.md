# Source-bound finite fabrication search

`routing/certified_fabrication.py` connects the finite direction/straight-debt
fabrication graph to the complete physical support ledger produced by the
source-bound IFC cell adapter. Ordinary and simultaneous routing invoke it
after the direct baseline and source support computation. A successful nominal
path is materialized and subjected to the normal complete independent IFC
checker before selection or acceptance.

The adapter verifies the original report identity, current geometry dependency
hashes, exact scenario, complete source path/hash/frame sequence, and full
physical coverage. Source bytes are freshly hashed before and after search.
This consumes a current local producer's source-support report; hashes are not
signatures against a coherently forged report or hostile cache. Original native
conversion and exact-source-support assumptions remain attached explicitly.

Ball-path omissions are not transferred. Every loaded obstacle receives a new
disposition against the entire permitted body region: either a rational plane
strictly separates its complete support box by the required clearance, or it is
contained in a retained outer union box. An independent checker verifies the
complete denominator, every group enclosure and every exclusion inequality.
This avoids dependence on a rounded ball radius or a smaller centre domain.
Grouping can prevent discovery of a feasible route; it never proves physical
collision or whole-route infeasibility.

Grid axes use exact derived diameter/2 + insulation to erode the allowed region,
and include the exact fixed terminals. The bounded kernel retains incoming
direction, last straight-run origin and bend trim debt. Its independently
reconstructed path/cut proof applies only to the declared finite graph.
Defaults are four subdivisions, 12,000 states, 150,000 work units and 128 outer
groups. Integration additionally limits elapsed time and preserves worker
cancellation. An unavailable or exhausted graph yields no physical impossibility
claim and does not disable other proposal methods.

Converting a path to binary64 is a separate change. The adapter recompiles and
independently checks the complete resulting nominal straight/quarter-torus body,
its allowed-region bounds and every retained outer group. Only a passing
fabrication disposition becomes a proposal. This does not prove exact equality
to numerical IFC solids: actual geometry, complete obstacle and self-contact
checks, ports, protected contents, mission and requested service remain required.

`tests/test_certified_fabrication.py` includes a real native IFC wall: complete
source support → finite fabrication search → independent graph proof → binary64
body proof → actual materialization → full native clearance. It also tests
missing/duplicate support, false grouping/omission, changed source bytes and
frames, strict clearance boundaries, deadline and cancellation. The regular
ordinary/joint integration tests require this proposal method, then exercise
acceptance, fresh exported copies, preserved earlier route proofs and relocation.
