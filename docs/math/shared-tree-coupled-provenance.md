# Fixed-ID unequal-pressure catalogue provenance

This extension allows generated nominal shared-tree catalogues for the existing explicit `CoupledTreeBoundary` contract. Every declared pressure tee keeps its physical ID, authored site/frame and named `b`/`branch` loss coefficients. The generator may vary connector paths, root/child topology and sink/outlet assignments. It must not relabel losses or rewrite pressure requirements to fit a generated alternative.

The independent API remains `verify_generated_catalogue(requirements, search, generated, *, context, max_work=2_000_000, max_bytes=16_777_216, max_macros=1024, max_attempts=20000, checkpoint=None)` in `oma.routing.shared_tree_catalogue_check`. Its PASS remains a supplied-catalogue provenance result, with **no hydraulic, native feasibility, all-template completeness or acceptance authority**.

## Exact specialization

The extension requires two or three sinks and exactly n-1 authored tee instances. Their distinct IDs must equal `coupled_tree.tee_outlet_loss_coefficients.keys()`. Each ID therefore has one authored geometric instance. The pure finite topology kernel already proves every complete binary tree uses n-1 distinct tees. Together these conditions imply every admitted complete assignment uses all and only the declared pressure tee IDs. No ranked-prefix postfilter or role-to-site renaming is needed.

The complete coupled boundary is parsed by the unchanged `CoupledTreeBoundary` model and compared with its canonical normalized form. It retains every source/sink total-pressure interval, exact minimum delivery, exact flow proof-proposal box, density, Darcy factor, gravity, elbow loss, velocity limit and explicit loss/ideal-bore/boundary/applicability statement. Sink IDs must match all pressure/minimum/box identities. Fixed sink flows and static budgets are forbidden in this profile. It requires a pressure-pipe engineering-service mission and `physics=None`. Other generated pressure profiles (`passive_tree`, `pressure_driven`) remain explicitly UNKNOWN, including attempts to combine them with this mode.

Each tee's loss root is independently recomputed as:

```text
digest({
  "model": "oma.coupled-tree-boundary/1",
  "tee_id": current_physical_tee_id,
  "outlet_coefficients": normalized_boundary.tee_outlet_loss_coefficients[id],
  "boundary_root": digest(normalized_boundary)
})
```

The entire raw requirements/search/context root and normalized requirement root still bind the catalogue and each current fabrication certificate. This is stronger than just checking the coefficient key set. A record assigning another tee's coefficients or swapping `b` and `branch` fails even if its hash is freshly resealed and all physical IDs still occur once. The original fixed-flow loss identity remains exactly `digest(normalized_requirements.get("physics"))`.

All independent nominal checks from the base checker remain: exact cap directions and section, binary64-representable promised geometry, finite template membership, fresh independent orthogonal fabrication replay, directly reconstructed segment/elbow geometry and nominal rational-plus-pi cost, unique component IDs, and complete connector/macro/admitted-attempt incidence. Rejected-attempt diagnostics still carry no independently certified rejection or template-completeness claim. Strict parsing, numeric/byte/work bounds, caller exception identity and final no-callback mutation guards are retained.

## Unchanged physical proof boundary

The mathematical pressure law is not changed. Each tee outlet loss is proportional to that tee's **total inlet descendant flow squared**, applied only to the sink rows using that outlet. Tee skeleton Darcy loss is not added. Unequal outlet heads are not contracted into a common head. Per-component diameter/length/area and every port elevation come from the current native-metric adapter and its declared uncertainty and ideal-bore scope, not the nominal macro certificate.

Every generated physical candidate still requires full native source/self/contact/zone checks and the existing independently reconstructed coupled model. The operating-point obligation needs both current local Banach and global nonnegative-univalence checks, with the same complete model/parameter roots. The global singleton-resistance premise is not inferred from a nominal catalogue. Forward port flow, exact minimum deliveries and all-port velocity are separate service obligations. Missing or unresolved proofs retain UNKNOWN/BLOCKED and cannot be promoted by nominal ranking.

The search box is preserved as a fixed proof-proposal range. Failure to certify an alternative inside that box does not prove physical infeasibility. Nominal length/fitting cost is not a pumping-energy objective or a native lower bound. A finite output prefix may omit a later hydraulically admissible tree; no complete physical search claim follows.

The complete generated scenario's menu-dependent hashes change when designs change. Fixed requirements are compared through the existing canonical projection that removes only the explicitly replaceable alternative menu. The exact coupled boundary and original authored request remain unchanged. Source authentication, current execution, native metric authenticity, admission, acceptance and exported-IFC replay remain caller obligations.

## Source and design evidence

Original unchanged source: `math1/math1/the 5 things that combine ceiling router with ananke.docx`, SHA256 `72379f535f744b15ccbdcbbb6f68904f6c1177ace27a8fcc028229039b8bd129`. The bounded synthesis/provenance basis is ADD-SIR2.1 P3787-P3806, DEF-RTR39-45 P4472-P4517, THM-RTR50-53 P5254-P5265 and ALG-RTR17-22 P5526-P5537. The extension connects the already checked physical-fiber model to generated alternatives; it does not complete any full source algorithm.

The read-only precursor is `.oma/development/shared-tree-coupled-design/design.md`. Its exact abstract oracle enumerates 24 three-leaf labeled templates and demonstrates a nonzero path-law residual when distinct tee coefficient records are swapped. It makes no cap-geometry or native operating-point claim. Multiple possible sites per persistent tee role remain a separate design requiring checked role/site assignment and complete finite ranking; this extension supports one authored site per fixed ID.

## Frozen validation

New module SHA256: `c800938e03909fcbe8a014e21b46c9640ddf5736fe3684f345bdd57a5bfb7fd4`. Exact component/test/fixture snapshot: `0f780ef00357d14887bdb067263b8ed891cddeed91aa7ccdc5169e3ebf1a7a29`, against unchanged 110-file dependency root `84f32e8666cdb1b17fb2cda1021d5bad28970a28568b1bccc7e9c93d53cf69ed`. These are private component/dependency identities, not a full production executable identity.

Receipt `validation/54efc47c0e9243fda34e92526cda3f9c` records 164 exact collected/executed tests, zero skips/failures/errors, and unchanged source/test/fixture/dependency hashes. It includes the original 94 checker cases plus 70 extension cases: one-tee/two-sink and two-tee/three-sink fixtures; the independently authored parent's 28-macro three-sink packet; complete role/sink/profile/domain negatives; resealed outlet/role/boundary identities; changed pressure/minimum/query-box assumptions; exact work and final callbacks; producer/pressure-solver-disabled replay; full generated `NetworkDesign` to `SharedNetworkScenario` validation; and byte-identical legacy output against frozen base checker `688cb03a`.

The two local fixtures are explicitly nominal-provenance-only declarations. Their authoring script uses the retained original nominal producer/fabrication authoring helpers to create immutable test data; the independent verifier does not invoke them. Their arbitrary valid pressure declarations are not claimed to have a certified operating point. The third packet was independently predeclared by the parent before generation, with retained exact pressure-manufacturing evidence. The test checks its catalogue and unchanged requirements, not native hydraulics or acceptance.

The original isolated implementation changed no production module or prior frozen checker. The final extension is now integrated; those earlier component receipts remain historical. Base `688cb03a`, its 94-test receipt, earlier resource-failure evidence and independent actual-workflow peer replay remain distinct preserved checkpoints. The integrated generated coupled native workflow is documented in `docs/shared-tree-generation.md`, with separate complete regression and native evidence.
