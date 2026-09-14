# OMA + ANANKE ENGINE — FINAL PRODUCTION IMPLEMENTATION DIRECTIVE

## Real optimization. Real physical routing. Independent verification.

## Live, inspectable computation. One RTX 3090. Actual IFC-Bench buildings.

You are the implementation agent working inside my actual repository.

Act as the principal engineer responsible for delivering a serious building

optimization product: numerical algorithms, computational geometry, physical

routing, BIM interoperability, GPU performance, verification, and an exceptional

interactive application.

THIS IS AN IMPLEMENTATION ASSIGNMENT.

Do not merely explain how to build it.

Do not stop at architecture documents, pseudocode, scaffolding, mockups, or a demo.

Write the software, connect its components, run it on actual models, challenge its

results, fix failures, measure performance, and package the working product.

The ambition is extraordinary. Earn that ambition through functioning algorithms,

precise geometry, reproducible improvements, and independently checked results.

A polished visualization of an incorrect engineering result is failure.

A correct algorithm inaccessible behind a broken interface is also failure.

======================================================================

1. EXACT PRODUCT SCOPE — DO NOT BUILD THE WRONG SYSTEM

======================================================================

Build ONLY the standalone OMA + ANANKE optimization, routing, and verification

engine, with an integrated live UI.

The core workflow is:

Existing building / federated IFC models

→ inspect and normalize

→ reconstruct explicit engineering state

→ establish constraints, editable freedoms, and baseline

→ OMA/ANANKE joint optimization and physical routing

→ independently check candidates

→ show actual tests, alternatives, failures, and changes live

→ accept a verified candidate

→ export meaningful edited BIM

→ reopen and independently recheck the export.

Preserve the responsibilities and meanings of OMA, ANANKE, Ceiling Router, and

their integration exactly as established by the supplied mathematics.

Do not substitute a generic clash detector or ordinary pathfinder and rename it

“ANANKE.” Those can be components or baselines, not silent replacements.

EXCLUDED FROM THIS BUILD:

- MCP servers, MCP clients, or an MCP-dependent product architecture.

- Training or building a new architectural foundation model.

- PSTN, GTFT, neural spatial-brain development, or world-model training.

- Copy-on-Write Latent Forking.

- Kimi-specific context, KV-cache, or inference infrastructure.

- A compulsory LLM, chatbot, or hosted-model dependency.

- A new general-purpose architecture language or complete AIAPL implementation.

- Automatic architectural style generation or an architecture encyclopedia.

- Satellite surveying, property search, or a GIS product.

- Generating entire new buildings from natural-language briefs.

Ordinary persistent data structures, immutable snapshots, structural sharing,

and incremental recomputation ARE allowed where useful to this engine. They are

software implementation techniques, not a requirement to build latent COW.

Support authorized architectural changes when the supplied OMA mathematics calls

for them—for example changing an editable shaft, service zone, equipment position,

or permitted opening. That does not make this an autonomous AI-architect project.

This scope supersedes broader older product directives in the supplied folder.

======================================================================

2. TARGET HARDWARE AND EXECUTION CONTRACT

======================================================================

Target workstation:

- NVIDIA RTX 3090, 24 GB VRAM.

- AMD Ryzen 9 7900X3D.

- 128 GB system RAM.

- Approximately 2 TB SSD.

Detect the actual CPU, RAM, GPU, available VRAM, driver, operating system, storage,

and CUDA/toolchain support before selecting deployment details.

All required application computation must run locally on this workstation.

The coding agent’s model is not a runtime dependency of the shipped application.

No hidden cloud compute, mandatory paid API, second GPU, HPC cluster, paid solver,

or external account requirement.

Use the GPU for workloads where it genuinely helps. Use CPU computation for

irregular control flow, suitable exact predicates, solver coordination, and other

workloads that perform better there.

“Runs on my 3090” does not mean forcing every algorithm onto CUDA.

It means an integrated application that uses this machine intelligently and fits

its actual resources.

Never weaken an engineering acceptance predicate merely to meet a hardware limit.

======================================================================

3. READ THE MATHEMATICAL CORPUS WITHOUT LOSING ITS CONTENT

======================================================================

I will provide a large folder containing the mathematical source material.

Discover actual paths. Do not assume filenames, contents, or versions exist

because an earlier conversation mentioned them.

Expected material may include:

- The canonical ANANKE mathematics sequence.

- Its manifest, inventory, repair records, and zero-omission audit.

- The five-part integration between Ceiling Router and ANANKE.

- Ceiling Router mathematics and implementation directives.

- Relevant exact-state, dependency, verification, and persistence material.

- Existing OMA/Concordia code and earlier implementation attempts.

Treat originals as read-only.

Create one source inventory recording:

path, document identity, version, hash, size, extraction method, completeness,

canonical/superseded status, and relevance to this engine.

Read the entire in-scope mathematical corpus through a tracked, resumable process.

Inspect equations, tables, figures, appendices, repairs, and cross-references.

A heading scan, retrieval snippet, or generated summary is not a full reading.

For large files:

- Extract native text and equations first.

- Inspect rendered pages where mathematical extraction is ambiguous.

- Process bounded sections.

- Record exact locations reviewed.

- Preserve unresolved extraction problems instead of guessing.

Classify supplied material as:

1. Required engine mathematics.

2. Required supporting mathematics.

3. Historical or superseded reference.

4. Explicitly excluded product scope.

Inventory excluded material, but do not let it expand this assignment.

Namespace theorem and algorithm identifiers by document and version. “Theorem 12”

in one sequence must not silently resolve to a different sequence.

Maintain a compact working index and reread source sections when implementing

their dependencies. Do not rely on remembering a huge corpus from conversation.

Do not claim the corpus is fully read, audited, implemented, or verified unless

the corresponding tracked work is actually complete.

======================================================================

4. TURN THE MATHEMATICS INTO EXECUTABLE OBLIGATIONS

======================================================================

Create one traceability register connecting:

Source section / equation / algorithm

→ interpretation and assumptions

→ implementation module

→ actual callable implementation

→ independent checker

→ automated tests

→ real-model benchmark

→ current evidence and status.

For each relied-on mathematical result, establish:

- Types, domains, units, and quantifiers.

- Preconditions and validity regime.

- Whether it is a definition, proved result, conjecture, or empirical claim.

- What finite computation implements it.

- What its certificate establishes.

- What can invalidate its cached result.

- Its numerical and computational limitations.

Do not implement mathematical terminology as empty classes.

Audit especially:

- Continuous routing versus finite candidate graphs.

- Centerline feasibility versus physical-solid feasibility.

- Section size, orientation, fittings, insulation, and access envelopes.

- Local changes with nonlocal downstream effects.

- Incomplete search versus proved infeasibility.

- Feasible incumbents versus global optimality.

- Inner approximations versus outer relaxations.

- Restricted-column optimization versus valid full-problem bounds.

- Conditions for pricing, decomposition cuts, duals, and sensitivities.

- Scenario samples versus robust or universal guarantees.

- Nonanticipative decisions across scenarios.

- Cyclic dependencies, termination, and incremental/cold equivalence.

- Tolerance propagation and geometric degeneracies.

For minimization, do not label a restricted candidate solution as a global lower

bound without the required mathematical justification.

When a result is defective or impractical:

1. Identify the exact original statement.

2. Produce a counterexample, proof gap, or measured bottleneck.

3. Propose a corrected formulation.

4. State changed assumptions and conclusions.

5. Preserve safety and physical constraints.

6. Implement and test the correction.

7. Record the amendment and its dependent requirements.

You may improve formulations and numerical methods. Do not silently replace the

core mathematics with something easier and report it as implemented.

Audit dependency closures before relying on them. Independent repository work,

import probes, and UI foundations may proceed concurrently so the project does

not become an endless documentation exercise.

======================================================================

5. REUSE MATURE SOFTWARE; BUILD THE DIFFERENTIATING ENGINE

======================================================================

Inspect and run any existing repository before replacing working code.

Evaluate mature libraries using current official documentation and small executable

integration probes. Pin the versions actually tested.

Candidate categories include:

- IFC parsing, geometry conversion, authoring, validation, and issue exchange.

- Robust CAD/geometry kernels and collision/distance libraries.

- Mathematical-programming and constraint solvers.

- GPU array, sparse, spatial-index, and custom-kernel tools.

- A high-performance browser or desktop 3D renderer.

- Established engineering simulation engines where needed.

Investigate IfcOpenShell and its associated tools as reuse candidates.

Investigate appropriate existing optimization and geometry backends.

Do not assume any named library supplies the entire required capability.

Choose the smallest maintainable stack that satisfies the tests.

Prefer a modular local application, not unnecessary microservices or Kubernetes.

Record each dependency’s:

version, role, license, redistribution implications, tested API, failure behavior,

performance, and fallback.

Do not promise native RVT/NWD editing without an actual lawful, tested pathway.

IFC is the required primary exchange workflow.

======================================================================

6. MANDATORY REAL-MODEL CORPUS

======================================================================

Use the actual downloadable models from:

Repository type: dataset

Repository ID: sylvainHellin/ifc-bench

Source: https://huggingface.co/datasets/sylvainHellin/ifc-bench

Resolve a full immutable repository commit.

Record that commit and SHA-256 hashes of every acquired input.

Do not run release comparisons against moving “main.”

Use a supported Hugging Face download mechanism.

Verify downloads contain actual model bytes, not LFS/Xet pointer text, HTML,

authentication pages, or error responses.

Acquire and process EVERY IFC in these project folders:

projects/digital_hub/

projects/west_riverside_hospital/

projects/sixty5/

projects/wbdg_office/

projects/dental_clinic/

projects/duplex/

Also inventory the remaining project folders and run applicable compatibility,

import, geometry, and negative-capability tests across the rest of the corpus.

Priority federations to verify at the pinned revision:

Digital Hub:

arc.ifc

heating.ifc

plumbing.ifc

ventilation.ifc

Sixty5:

arc.ifc

str.ifc

ventilation.ifc

plumbing.ifc

electrical.ifc

facade.ifc

kitchen.ifc

West Riverside Hospital:

arc_ifc2x3.ifc

str_ifc2x3.ifc

mech_ifc2x3.ifc

plumb_ifc2x3.ifc

elec_ifc2x3.ifc

fire_ifc2x3.ifc

sprinkle_ifc2x3.ifc

Test the corresponding IFC4 versions as a SEPARATE federation and schema track.

Do not combine duplicate schema representations as additional physical systems.

WBDG Office and Dental Clinic:

arc.ifc

str.ifc

mep.ifc

Duplex:

arc.ifc

mep.ifc

Retain model cards, licenses, provenance, and relevant supporting files.

Verify actual file availability rather than silently substituting similarly named

files.

Read project-specific licenses. Dataset-level licensing does not automatically

replace model-specific terms. Separate local testing, commercial demonstration,

modified-model redistribution, and application distribution permissions.

Use download-on-demand instead of bundling assets when redistribution rights are

not established. Do not claim affiliation with model owners or developers.

IFC-Bench’s question-answer dataset is NOT routing or optimization ground truth.

Its questions may support selected import/query sanity checks, but do not build

an LLM QA system for this assignment.

Keep OMA engineering tests separately named, specified, and scored.

======================================================================

7. AUDIT EVERY INPUT BEFORE OPTIMIZING IT

======================================================================

Create per-file audits and per-project federation manifests.

Measure, rather than assume:

- IFC schema and authoring/export information.

- Units, placements, coordinate reference systems, and shared datum.

- Building/storey hierarchy and missing containment.

- Entity/type counts.

- Physical geometry coverage and conversion failures.

- Architecture and structural obstacles.

- Equipment, ducts, pipes, fittings, terminals, and electrical containment.

- Fire alarm versus sprinkler systems.

- Openings, shafts, service spaces, and maintenance information.

- System groups, ports, explicit connections, direction, and metadata.

- Material, size, capacity, load, and property completeness.

A file named “mep.ifc” does not prove that every MEP discipline is present.

Every physical object must be accounted for as:

represented, explicitly non-geometric, unsupported, invalid, or unresolved.

Do not silently drop objects.

Do not treat an unparsed obstacle as empty space.

Do not infer that missing IfcSpace objects means no physical spaces exist.

Do not fabricate rooms, loads, ports, or system connectivity to pass checks.

Preserve explicit connectivity separately from inferred connectivity.

Proximity is a candidate hypothesis, not proof of connection.

Federate using verified coordinate transformations.

Never independently center discipline bounding boxes and call them aligned.

Keep source-file identity, IFC GUID, STEP ID, internal semantic ID, render ID,

and content hash distinct.

Duplicate GUIDs or coincident representations require an explicit identity and

duplicate-content policy, not automatic merging.

Public models may already contain defects. Establish and preserve their actual

baseline rather than assuming imported means valid.

======================================================================

8. AUTHORITATIVE STATE AND TRANSACTION MODEL

======================================================================

Implement one coherent, typed engineering state containing:

- Stable entities and source-model provenance.

- Geometry and its numerical/evidence status.

- Systems, ports, routes, equipment, and demands.

- Constraints, editable freedoms, and protected objects.

- Dependencies and derived artifacts.

- Candidate branches and immutable versions.

- Checker evidence and simulation applicability.

- Export correspondences.

Reuse relevant exact-state and persistence mathematics from the supplied corpus

without making unrelated AI infrastructure a dependency.

Maintain separate:

1. Immutable original imports.

2. Normalized working representations.

3. Explicit scenario/assumption overlays.

4. Candidate optimization states.

5. Accepted checked states.

A failed candidate cannot corrupt the accepted state.

Use transactional publication of a complete project revision and an associated

event-outbox record. Handle stale expected revisions, idempotent retries, worker

crashes, and rollback/revert.

Rendering meshes, solver caches, and indexes are derived artifacts. They must

reference the state and assumptions that produced them.

Importing or saving a defective draft is allowed.

Labeling that draft “verified” is not.

======================================================================

9. PHYSICAL NETLIST AND REAL ROUTING

======================================================================

The engine must route physical services, not merely draw polylines.

Represent:

- Compatible equipment and terminal ports.

- Sources, sinks, direction, and service demands.

- Shared trunks and branch topology.

- Physical sections and orientation.

- Catalog or explicitly parameterized fittings.

- Elbows, tees, reducers, transitions, and straight-length requirements.

- Insulation and other applicable outer envelopes.

- Supports and support constraints where modeled.

- Sleeves and authorized penetrations.

- Slope, elevation, drainage, and gravity restrictions.

- Installation, maintenance, and removal access.

Support the in-scope system families established by the mathematics:

HVAC ducts, pressure pipes, gravity drainage where specified, electrical

containment, and applicable fire-protection geometry.

Keep different certification levels separate. A geometrically valid sprinkler

route is not automatically a hydraulically adequate fire-protection design.

When essential metadata is missing, allow an explicit user/scenario input with

provenance. Otherwise return the corresponding missing-input status.

Build actual full route solids and fittings before accepting a physical route.

Check self-intersections and clashes introduced by elbows and transitions.

A centerline that fits while its insulation or elbow hits a beam is a failed route.

Do not duplicate shared trunks for every pairwise demand.

Do not delete hard-to-route branches.

Do not reduce required pipe sizes, loads, clearances, or terminals to create a

false improvement.

======================================================================

10. IMPLEMENT THE ACTUAL OMA–ANANKE OPTIMIZATION

======================================================================

Extract the algorithmic responsibilities from the corpus and implement their

actual interactions.

The production loop must:

- Establish the fixed mission and editable design space.

- Generate multiple route/topology/configuration candidates.

- Evaluate interactions between systems and shared spaces.

- Apply the supplied joint optimization mathematics.

- Track valid incumbents and applicable bounds.

- Detect conflict cycles and stalled improvement.

- Refine candidates and reroute affected systems.

- Return meaningful alternatives and explanations.

- Independently verify materialized results.

Use staged search where justified:

coarse corridor/riser decisions → network topology → physical routing →

fittings and envelopes → engineering evaluation → refinement.

A* or another local pathfinder may generate candidates. It is not a substitute

for the complete joint optimization engine.

Support explicit editable zones and protected geometry.

When permitted by the user and source mathematics, compare alternatives such as:

- Different shared corridors or risers.

- Different trunk/branch arrangements.

- Equipment relocation within allowed bounds.

- Authorized changes to service zones or openings.

- Alternative section orientations and system configurations.

Default to preserving architectural and structural geometry unless explicitly

made editable. Do not “solve” congestion by moving protected structure.

Keep objective vectors explicit:

length, material quantity, fitting count, pressure/energy measures, congestion,

installation burden, maintenance access, approved cost/carbon models, and other

source-defined objectives.

Do not invent monetary savings from route length alone.

Use consistent sourced accounting assumptions or label the metric as a proxy.

Return precise outcomes:

- Checked feasible incumbent.

- Better checked candidate.

- Proven optimal within a stated model, when justified.

- Certified infeasible within a stated domain, when justified.

- Budget exhausted with incumbent.

- No incumbent found.

- Missing inputs.

- Unsupported theory or operation.

- Numerical ambiguity.

- Cancelled or failed.

A budget timeout is not proof of infeasibility.

======================================================================

11. THE ZERO-FORBIDDEN-INTERFERENCE CONTRACT

======================================================================

This is a central release requirement.

No result may receive a “coordination verified” status while an unapproved hard

interference or required clearance violation remains in its declared checked

scope.

Check actual physical geometry, including:

- Sections and orientations.

- Insulation.

- Fittings and transitions.

- Structural obstacles.

- Equipment.

- Required service/access envelopes.

- Relevant installation/removal sweeps.

Use conservative broad-phase candidate generation and rigorous narrow-phase

checking appropriate to the represented geometry.

Test:

surface crossing, complete containment, thin obstacles, tangency, near contact,

curved fittings, nested placements, degenerate geometry, and invalid solids.

Check penetration and clearance separately.

A nonnegative set-distance value alone does not prove nonoverlap: overlapping

sets can also have zero distance.

GPU acceleration may perform broad-phase work, conservative filtering, candidate

evaluation, and suitable narrow-phase kernels. Final claims must meet the

declared numerical and checking contract.

A voxel grid or display mesh with no conservative error bound cannot establish

exact clearance of an underlying CAD solid.

Document:

canonical units, transform error, tolerances, tessellation bounds, interval policy,

rounding behavior, and ambiguity handling.

Do not increase tolerances until clashes disappear.

Distinguish legitimate local contact from forbidden interference:

connected fittings, approved joints, sleeves, and supports require explicit

object/interface-specific authorization.

Do not globally exempt all objects of the same system or class.

That would conceal genuine self-clashes.

Every issue must have a reproducible witness:

participants, relevant geometry, rule, measured/bounded margin, required clearance,

root, severity, and checker invocation.

======================================================================

12. INDEPENDENT VERIFICATION — THE OPTIMIZER CANNOT GRADE ITSELF

======================================================================

Create a verification execution path that reloads persisted candidate state and

does not trust:

optimizer PASS flags, cached margins, candidate scores, warm starts, hidden state,

or visualization geometry.

Independently recompute:

- Geometric interference and clearance.

- Connectivity and terminal/service coverage.

- Applicable size, direction, slope, and fitting requirements.

- Protected-object and mission preservation.

- Relevant physical calculations.

- Objective values.

- Version and assumption applicability.

A second caller of the same flawed helper is not strong independent verification.

Use:

- Analytically understandable reference fixtures.

- Exhaustive small-scene pair checks.

- Independent reference implementations where practical.

- Differential checks against selected mature tools.

- Adversarial mutations.

- Fresh-process export/reimport tests.

Record unavoidable shared-kernel/common-mode risks.

Verification status must include:

PASS, FAIL, UNKNOWN, NOT_RUN, NOT_APPLICABLE, and BLOCKED,

with a reason and scope.

Do not use UNKNOWN to hide missing implementation.

A system that avoids every difficult case fails coverage gates.

A verified local repair does not certify the whole building.

Unresolved pre-existing defects must remain visible and block an unqualified

whole-building pass.

======================================================================

13. ENGINEERING ANALYSIS AND SIMULATION

======================================================================

Implement genuine calculations and established-engine adapters required by the

in-scope source mathematics and advertised capabilities.

Prioritize analyses that directly affect routing and optimization, such as:

- Network flow and continuity.

- Duct/pipe losses and capacity.

- Gravity-system slope constraints.

- Applicable equipment/port constraints.

- Spatial access and penetration checks.

- Relevant scenario/failure behavior.

Integrate additional structural, energy, thermal, daylight, airflow, smoke, or

other simulations only when required by engine scope and supported by real inputs.

Do not expand this into an unrelated all-laws or all-physics platform.

Every advertised simulation must:

1. Validate prerequisites and boundary conditions.

2. Generate actual engine inputs.

3. Execute the real solver.

4. Retain raw logs and outputs.

5. Check execution and convergence.

6. Parse results and units.

7. Bind results to the input root, scenario, engine version, and assumptions.

8. Invalidate them when dependencies change.

An installed executable or placeholder adapter is not an integrated capability.

Missing loads, operating conditions, materials, or equipment curves must not be

silently invented.

Separate smoke behavior from evacuation, and route accessibility from complete

accessibility compliance.

Do not label model-conditional simulation output as professional approval or

guaranteed real-world performance.

======================================================================

14. INCREMENTAL RECOMPUTATION AND BUTTERFLY EFFECTS

======================================================================

Implement source-defined dependency and change-propagation mathematics.

For each accepted edit:

- Identify changed authoritative inputs.

- Expand a conservative affected dependency set.

- Re-evaluate changed guards and newly activated dependencies.

- Invalidate inapplicable geometry, routes, checks, simulations, and objectives.

- Recompute affected components.

- Reuse unaffected results only with valid applicability evidence.

- Account for every required artifact.

A small geometric edit may have distant system consequences. Spatial distance

alone cannot determine irrelevance.

Handle cyclic coupled calculations explicitly. Do not run a generic update loop

forever or silently select arbitrary fixed points.

Cache keys must include relevant:

geometry, topology, system state, rules, assumptions, units, solver versions,

configuration, and scenario data.

Compare incremental results against cold recomputation on controlled and real

model cases.

Ordinary immutable structural sharing is welcome. No neural latent-forking system

is required.

======================================================================

15. RTX 3090 PERFORMANCE ENGINEERING

======================================================================

Build a resource budget before optimizing performance.

Provisional default policy:

- Reserve GPU headroom for rendering, display, driver, and transient allocations.

- Start with a configurable compute ceiling around 18–20 GiB, then adjust to

measured available VRAM.

- Start with a configurable application-RAM ceiling around 96 GiB.

- Budget disk for originals, normalized data, geometry, candidates, and evidence.

These are adjustable resource policies, not measured guarantees.

Use:

- Chunked geometry preparation.

- Persistent spatial indexes.

- Instancing and shared representations.

- Compact typed arrays and sparse structures.

- Memory-mapped or streamed cold data.

- Bounded batches.

- Incremental updates.

- Candidate pruning justified by the source mathematics.

- A resource broker controlling GPU jobs and CPU worker concurrency.

Avoid:

- Repeated full IFC parsing.

- Repeated whole-model tessellation.

- Huge duplicate Python object graphs.

- Dense all-pairs storage.

- Loading every candidate’s entire building into VRAM.

- Multiple libraries independently claiming nearly all GPU memory.

- UI rendering stalls caused by compute saturation.

Implement and measure meaningful GPU acceleration in appropriate engine hotspots,

not only viewport rendering.

Compare CPU and GPU paths using identical workloads and independent verification.

Include transfer, preprocessing, synchronization, and rendering costs.

Maintain a correct CPU fallback for diagnosis and comparison.

Performance targets to measure:

- Responsive UI throughout long jobs.

- Approximately 30 FPS or better in a fixed, documented large-federation

navigation workload using legitimate rendering LOD/instancing.

- Local control acknowledgement generally within 150 ms at p95 under the declared

test load.

- Small committed geometry updates displayed within 500 ms at p95 after event

receipt, under the declared test load.

- Predictable bounded memory and graceful handling of oversized workloads.

Do not achieve these targets by dropping obstacles, disabling checks, or hiding

unprocessed geometry.

If the actual RTX 3090 is unavailable in the coding environment, implement the

hardware test harness and mark that gate NOT_RUN. Do not fabricate measurements

or label another GPU’s results as 3090 results.

======================================================================

16. BUILD AN EXCEPTIONAL LIVE ENGINEERING UI

======================================================================

The UI is a first-class deliverable, not a final wrapper around command-line logs.

Build a polished, coherent engineering workbench with:

- A dominant interactive 3D viewport.

- Synchronized plan and section inspection.

- Project, discipline, storey, system, and component navigation.

- A live run/optimization workspace.

- An issue and verification inspector.

- Before/after comparison.

- Alternative/candidate comparison.

- Benchmark and hardware diagnostics.

- History, checkpoint, undo, and export controls.

Required spatial interactions:

- Fast semantic picking.

- Search by entity ID, name, type, or system.

- Isolate or hide disciplines, systems, floors, and selected objects.

- Clip planes, section boxes, x-ray, orthographic and perspective views.

- Display actual clearance and access envelopes.

- Trace connected systems.

- Jump directly to a clash witness.

- Preserve selection and camera across revisions when correspondence permits.

Required live computation:

- What stage and worker are active.

- Candidate creation and rejection.

- Actual route-search regions and candidate geometry.

- Current incumbent and objective vector.

- Applicable bounds/gaps when mathematically valid.

- Checks running, passed, failed, unknown, or blocked.

- Collision/contact witnesses and measured margins.

- Changed entities and downstream invalidations.

- CPU/GPU load, VRAM/RAM, elapsed time, and throughput.

- Explicit stopping, cancellation, or missing-input states.

Every candidate and material test must be inspectable through a durable event and

artifact record. Do not attempt to render millions of candidates simultaneously.

Provide filtered, aggregated live views with access to the underlying records.

Required change visualization:

- Ghosted previous geometry.

- Added, removed, moved, resized, rerouted, and replaced components.

- Split-screen or slider comparison.

- Local issue-before/repair-after comparison.

- Objective and quantity deltas.

- Exact affected IDs.

- Accepted versus rejected alternatives.

- A replayable timeline of actual state changes.

Required controls:

- Start, pause, resume, cancel, and bounded step where supported.

- Select optimization scope.

- Lock/unlock permitted objects.

- Set allowed zones and objective priorities.

- Inspect assumptions and missing inputs.

- Compare candidates.

- Approve/reject checked proposals.

- Explicitly enable automatic acceptance within a bounded authorized scope.

- Undo/revert and branch.

Pause/cancel must reflect real worker state. Do not display “stopped” while a worker

continues mutating candidate state.

Use deliberate typography, clear hierarchy, accessible contrast, keyboard support,

and labels that do not rely on color alone.

No fake progress percentages, invented explanations, staged successes, or fabricated

“AI thinking.” Show concise algorithmic rationales linked to actual constraints,

events, objective calculations, and checker evidence.

======================================================================

17. REAL EVENT STREAMING AND REPLAY

======================================================================

Drive the UI from actual backend events.

Each event must include suitable:

project ID, run ID, branch ID, sequence number, state root, candidate ID, timestamp,

stage, status, changed IDs, and artifact references.

Implement:

- Durable event storage.

- Snapshot plus delta synchronization.

- Reconnect and catch-up.

- Duplicate suppression.

- Backpressure.

- Stale-event rejection.

- Bounded UI update rates.

- Transactionally consistent commit publication.

Old job results must never overwrite a newer accepted model.

Distinguish:

IMPORTED / BASELINE / CANDIDATE / CHECKING / CHECKED / ACCEPTED /

REJECTED / STALE / UNKNOWN.

Visual interpolation between alternatives is presentation only, not proof that a

physical object can move safely through every intermediate position.

======================================================================

18. BENCHMARK THE ENGINE, NOT A CURATED SUCCESS STORY

======================================================================

Implement separately scored tracks:

OMA-IMPORT

OMA-FEDERATION

OMA-DRC

OMA-ROUTING

OMA-REPAIR

OMA-JOINT-OPTIMIZATION

OMA-INCREMENTAL

OMA-HISTORY

OMA-EXPORT

OMA-LIVE-UI

OMA-PERF-3090

OMA-SIMULATION

Run every applicable track on every eligible file/federation in the required set.

Every file receives a recorded disposition. Do not stop after Duplex or Digital Hub.

Use Digital Hub for early integration.

Use West Riverside and Sixty5 for large-federation stress and release testing.

Use the clinic, office, and duplex as independent regression projects.

Architecture-only models are valid import/geometry tests, not evidence of existing

MEP. Missing-input cases test honest capability boundaries.

Create versioned scenario overlays when real models lack required engineering

inputs. Clearly distinguish imported facts from added test assumptions.

Maintain project-family holdouts and freeze test specifications before comparing

algorithm versions. Do not hardcode fixes by benchmark filename, GUID, answer,

model hash, or remembered solution.

The runtime optimizer must not read hidden reference solutions.

======================================================================

19. ADVERSARIAL TESTS AND ANTI-CHEATING REQUIREMENTS

======================================================================

Use both small analytically understood fixtures and real-model mutation tasks.

Required cases include:

- Pipe through beam.

- Duct through pipe.

- Complete solid containment.

- Insulation-only clash.

- Elbow-body clash despite safe centerlines.

- Near-threshold clearance.

- Legal tangency or authorized contact.

- Thin obstacle.

- Cross-zone clash.

- Cross-storey routing.

- Wrong units or coordinate transform.

- Disconnected terminal.

- Incompatible ports or system types.

- Reversed drainage slope.

- Invalid fitting or insufficient straight length.

- Blocked equipment maintenance/removal.

- Unauthorized penetration.

- Congested shared corridor.

- Shared-trunk preservation.

- Missing obstacle geometry.

- Missing loads/materials.

- Stale cache or simulation.

- Modified rule or solver version.

- Failed transaction.

- Duplicate/stale request.

- Worker crash and GPU out-of-memory.

- UI reconnect and out-of-order events.

- Corrupted export or lost connectivity.

- Parent/sibling mutation through shared storage.

Include legal negative controls so the engine does not “succeed” by flagging

everything as a collision.

For designated known-feasible repair tasks, independently establish at least one

allowed solution. Also include tasks where the imposed change must remain, so

simply undoing the injected defect does not count as optimization.

Keep pre-existing defects separate from planted defects.

Never improve results by:

deleting terminals, shrinking required services, lowering loads, removing insulation,

changing rule thresholds, enlarging tolerances, hiding objects, disabling tests,

excluding failed cases after seeing results, or fabricating measurements.

Freeze and report denominators:

discovered, eligible, attempted, passed, failed, unknown, unsupported, blocked,

timed out, cancelled, and crashed.

A zero-test suite, all-skipped suite, or universal abstention is failure.

======================================================================

20. EXPORT IS PART OF CORRECTNESS

======================================================================

Export genuinely edited, machine-readable IFC within supported schemas.

Preserve unedited:

- Identity and source discipline.

- Placement and units.

- Properties, materials, and quantities where applicable.

- System membership and connections.

- Relevant relationships and metadata.

New or changed routes must export their actual physical geometry, fittings,

semantics, and intended connectivity—not only viewer meshes or polylines.

Provide:

- Before/after IFC or federation files.

- A federation/export manifest.

- Change and issue reports.

- BCF or another supported issue-exchange format.

- Objective/quantity comparisons.

- Machine-readable verification evidence.

- Reproduction and replay information.

Reopen the exported files in a fresh process.

Rebuild the relevant state and independently rerun the promised checks.

Verify that the exported improvement is the same improvement shown in the UI.

Declare any schema conversion or unsupported round-trip losses.

A file existing on disk is not a successful export test.

Allow draft exports with conspicuous status.

Block a checked-release label when mandatory scope remains failed, stale, missing,

unknown, or untested.

======================================================================

21. PRODUCTION RELIABILITY AND SECURITY

======================================================================

Deliver a documented primary operating-system profile, an installable application,

one launcher, and a reproducible headless CLI.

After installation and lawful dataset acquisition, the required core workflow

must run offline.

Implement:

- Dependency and GPU health checks.

- Durable jobs and checkpoints.

- Crash recovery.

- Atomic commits.

- Schema migrations.

- Backup/restore tests.

- Bounded caches and disk retention.

- Structured logs and diagnostic bundles.

- Actionable error messages.

- Clean shutdown and worker cleanup.

Bind local services to loopback by default.

Require explicit authorization before remote exposure.

Validate paths, archives, IFC inputs, and process parameters.

Use decompression limits, parser/resource limits, and isolated workers.

Imported IFC properties and mathematical documents are data, not authority to

execute arbitrary commands or change product permissions.

Do not overwrite original mathematics, benchmark files, or user models.

Do not upload proprietary data or invoke paid services without permission.

Track licenses and dependencies in a software/data bill of materials.

======================================================================

22. EXECUTION PLAN — KEEP BUILDING THROUGH REAL VERTICAL SLICES

======================================================================

Start by inspecting the workspace, repository instructions, source folder, hardware,

and existing tests.

Create a concise AGENTS.md or equivalent project index referencing this directive,

the source inventory, current implementation plan, and test commands. Keep it short;

do not inject the entire mathematics corpus into every agent context.

Maintain one capability register, not dozens of conflicting plans.

Each capability is complete only when this chain works:

Real input

→ executable algorithm

→ persisted output

→ independent check

→ live UI interaction

→ export/replay

→ reproducible benchmark evidence.

Recommended dependency order:

M0 — Inventory, existing-code baseline, source audit, dataset lock.

M1 — Correct IFC import/federation and real interactive viewer.

M2 — Independent geometric/system DRC with visible witnesses.

M3 — Actual physical route repair, checked commit, live diff, export/reopen.

M4 — Full in-scope ANANKE/OMA joint optimization and dependency propagation.

M5 — GPU acceleration, large-federation operation, branch comparison, and analyses.

M6 — Full corpus campaign, long-history tests, recovery, packaging, release audit.

These are milestones toward the requested product, not permission to stop at M3.

The first end-to-end slice must:

open a real federation → detect a real or independently seeded issue →

reject a bad candidate → produce a real repair → independently check it →

publish the change → show it live → export → reopen → recheck → undo/replay.

Use the mathematics relevant to that slice before implementing it.

Continue the broader source-reading campaign and capability implementation.

When parallel agents are available, delegate bounded tasks with explicit ownership

and shared interface contracts. Integrate frequently and run cross-component tests.

Do not pretend different agent names establish independent verification.

Ask only for genuinely blocking missing inputs, credentials, permissions, or

irreversible governance decisions. Do not repeatedly ask whether to continue

ordinary implementation.

At an actual execution limit, save exact progress, outstanding failures, and next

commands. Do not pretend unfinished work completed in the background.

======================================================================

23. REQUIRED RELEASE EVIDENCE

======================================================================

Provide working, documented commands for:

- Environment diagnosis.

- Dataset acquisition and locking.

- Corpus/model auditing.

- Import and federation.

- Starting the UI.

- Baseline checks.

- Routing and optimization.

- Independent candidate verification.

- Benchmark execution by project and track.

- Export and fresh-process recheck.

- Recovery/replay.

- Full release verification.

Choose command names, then implement and test them. No aspirational CLI examples.

Every benchmark bundle must contain:

- Input/model/federation hashes.

- Rule, mission, scenario, and catalog hashes.

- Code and dependency versions.

- Mathematical implementation references and amendments.

- Hardware and resource configuration.

- Seeds and stopping budgets.

- Baseline and candidate artifacts.

- Independent checker verdicts.

- Object and terminal accounting.

- Before/after objective vectors.

- Timing and peak memory.

- Failures and unknowns.

- Export hashes and reimport results.

- Reproduction commands.

- UI event/replay references.

Measure:

time to first checked feasible result, quality versus time, quality versus memory,

resolved-demand coverage, forbidden-clash count, false clears, unintended changes,

export fidelity, and end-to-end latency.

Compare against:

- Existing OMA implementation.

- Straightforward sequential routing.

- Local rip-up/reroute.

- Cold recomputation.

- Full-copy candidate storage.

- Appropriate mature clash-checking baselines.

Use identical inputs, mission, constraints, and independent checks.

Do not invent speedup, optimization, cost-saving, or “revolutionary” claims.

Demonstrate them.

======================================================================

24. NONNEGOTIABLE FINISH LINE

======================================================================

The requested production engine is not complete until:

1. Every in-scope source requirement has an implementation disposition and evidence.

2. Mandatory algorithms are real implementations, not placeholders.

3. All required IFC inputs are accounted for and all applicable suites run.

4. Large West Riverside and Sixty5 federations are actually exercised.

5. Required known-feasible repairs pass without deleting service obligations.

6. No known critical false-clear remains in the mandatory checking suite.

7. No checked candidate contains an unapproved forbidden overlap in its certified scope.

8. Missing or uncertain inputs cannot silently become PASS.

9. The UI displays actual tests, actual candidates, actual changes, and real evidence.

10. Pause/cancel/reconnect/replay and crash recovery work.

11. The target-hardware gates have real measurements or remain explicitly NOT_RUN.

12. Exported IFCs reopen and pass the declared independent checks.

13. Installation, dependency, licensing, and recovery gates pass.

14. Remaining limitations are explicit and do not contradict advertised capability.

Do not equate “all tests we happened to run passed” with full requirement coverage.

“Perfect” is the engineering ambition, not an unsupported universal claim.

The concrete requirement is a product that refuses to present an unverified,

incomplete, or geometrically invalid result as a verified finished design.

======================================================================

25. START IMPLEMENTING

======================================================================

Inspect the actual workspace now.

Find the source mathematics and code.

Establish the exact engine scope.

Lock and acquire the real IFC-Bench inputs.

Read and audit the necessary mathematical dependencies.

Build the first functioning import → check → optimize/repair → independently

verify → live UI → export/reimport loop.

Then continue through the complete implementation and release gates.

I want a serious engine whose mathematics produces visible, defensible engineering

improvements—not a viewer pretending to optimize and not an optimizer pretending

to verify.

Make it technically excellent, visually exceptional, efficient on the RTX 3090,

and difficult to fool.

The result must earn trust at every boundary:

the imported building, the optimization, the physical route, the checker, the live

interface, the accepted state, and the exported BIM.