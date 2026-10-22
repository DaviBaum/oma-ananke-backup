import { hospital } from "./hospital.js";
export { hospital, comparison } from "./hospital.js";

// Public demo data: aggregate counts from the retained Hospital runs.
// No source geometry, owner details, authenticated project prices, or private file paths.
// Keep the whole-building inventory and bounded route benchmark as separate claims.

export const project = {
  id: "hospital-reference",
  name: "Hospital example",
  shortName: "Hospital",
  subtitle: "Seven building design files, in one place.",
  type: "Healthcare",
  format: "IFC4",
  sourceCount: 7,
  productCount: 149822,
  serviceObjectCount: 45946,
  unresolvedProxyCount: 1770,
  candidateCount: 47716,
  portCount: 85602,
  connectionCount: 42801,
  systemCount: 790,
  componentCount: 5463,
  objectsWithoutPorts: 5008,
  branchedComponents: 207,
  cyclicComponents: 32,
  inventorySeconds: 129.672,
  evidenceDate: "2026-09-15",
  status: "Counted",
  scope: "Equipment, pipes and connections across the hospital",
  scopeNote:
    "All seven building design files are included. Some groups contain just one item with no recorded connections.",
  sourcePreservation: "Original files kept unchanged",
  engineeringStatus: "More design information needed",
  wholeBuildingOptimized: false,
  verifiedForConstruction: false,
  monetarySavings: null, // No verified whole-building net saving. See hospital for scoped purchasing estimates.
};

export const disciplines = [
  {
    id: "hvac",
    code: "M",
    label: "Heating & cooling",
    shortLabel: "Heating & cooling",
    color: "#2e8b79",
    products: 59215,
    objects: 19670,
    components: 340,
    ports: 39532,
    connections: 19766,
    systems: 466,
    objectsWithoutPorts: 159,
    status: "Counted",
    detail:
      "Heating and cooling equipment, ducts, pipes and their recorded connections.",
    designInput: "Required airflow, equipment capacity and supply conditions",
  },
  {
    id: "plumbing",
    code: "P",
    label: "Plumbing",
    shortLabel: "Plumbing",
    color: "#447eaf",
    products: 26942,
    objects: 9121,
    components: 313,
    ports: 17814,
    connections: 8907,
    systems: 65,
    objectsWithoutPorts: 264,
    status: "Counted",
    detail: "Water pipes, fittings, equipment and their recorded connections.",
    designInput: "Required water flow, available pressure and pipe materials",
  },
  {
    id: "electrical",
    code: "E",
    label: "Electrical",
    shortLabel: "Electrical",
    color: "#c18b36",
    products: 6305,
    objects: 2798,
    components: 1053,
    ports: 3498,
    connections: 1749,
    systems: 221,
    objectsWithoutPorts: 869,
    status: "Counted",
    detail:
      "Electrical equipment, lights, cable trays and conduits in the design files.",
    designInput:
      "Circuit power requirements, cable properties and installation rules",
  },
  {
    id: "sprinkler",
    code: "S",
    label: "Sprinklers",
    shortLabel: "Sprinklers",
    color: "#be675d",
    products: 38255,
    objects: 13490,
    components: 1120,
    ports: 24758,
    connections: 12379,
    systems: 17,
    objectsWithoutPorts: 1079,
    status: "Counted",
    detail:
      "Sprinkler pipes, fittings and equipment throughout the design file.",
    designInput: "Fire risk, required water flow and available water supply",
  },
  {
    id: "fire",
    code: "F",
    label: "Fire alarm",
    shortLabel: "Fire alarm",
    color: "#9172ad",
    products: 874,
    objects: 867,
    components: 867,
    ports: 0,
    connections: 0,
    systems: 21,
    objectsWithoutPorts: 867,
    status: "Counted",
    detail: "867 items counted. The files do not show how these items connect.",
    designInput:
      "Wiring connections, device requirements and control panel details",
  },
  {
    id: "architecture",
    code: "A",
    label: "Architecture",
    shortLabel: "Architecture",
    color: "#929389",
    products: 15316,
    objects: 1770,
    components: 1770,
    ports: 0,
    connections: 0,
    systems: 0,
    objectsWithoutPorts: 1770,
    status: "Needs identification",
    detail:
      "1,770 items have no clear equipment type. They stay visible for review.",
    designInput: "Identify the 1,770 items without a clear type",
    objectsLabel: "Items to identify",
  },
  {
    id: "structure",
    code: "ST",
    label: "Structure",
    shortLabel: "Structure",
    color: "#747c83",
    products: 2915,
    objects: 0,
    components: 0,
    ports: 0,
    connections: 0,
    systems: 0,
    objectsWithoutPorts: 0,
    status: "Counted",
    detail:
      "Structural items are kept and counted separately from building equipment.",
    designInput: "Structural performance is not assessed in this demo",
  },
];

export const routeComparison = {
  id: "two-terminal-pressure-pipe",
  title: "Four fewer bends. A simpler pipe route.",
  label: "Pipe route comparison",
  scope: "A pipe layout serving two outlets",
  scopeNote:
    "Two example pipe layouts were checked against the hospital's full architectural model. The results apply to this small test, not to the hospital's existing pipework.",
  architecturalObstacles: 14409,
  alternativesChecked: 2,
  baseline: {
    label: "Longer option",
    lengthM: 5.785398,
    fittings: 5,
    elbows: 4,
    components: 12,
    ports: 25,
    straightStockM: 4.625,
    interfaces: 11,
    pressureLossAPa: [51.6706, 51.6859],
    pressureLossBPa: [34.5239, 34.534],
    obstaclePairs: 172908,
    componentPairs: 66,
  },
  selected: {
    label: "Simpler option",
    lengthM: 5,
    fittings: 1,
    elbows: 0,
    components: 4,
    ports: 9,
    straightStockM: 4.625,
    interfaces: 3,
    pressureLossAPa: [37.7105, 37.722],
    pressureLossBPa: [34.5239, 34.534],
    obstaclePairs: 57636,
    componentPairs: 6,
  },
  improvements: {
    centerlineReductionPercent: 13.6,
    fittingReductionPercent: 80,
    demandALossReductionApproxPercent: 27,
    fewerElbows: 4,
    fewerModeledInterfaces: 8,
    straightStockReductionM: 0,
  },
  requirements: [
    "Each outlet must receive 0.5 litres of water per second",
    "100 Pa of pressure available to move the water",
    "Maximum water speed: 2 metres per second",
  ],
  checks: [
    {
      label: "Fits around the building",
      status: "Passed",
      note: "Checked against all 14,409 obstacles in the architectural model",
    },
    {
      label: "Pipe parts connect",
      status: "Passed",
      note: "The pipe ends and connections in the test were checked",
    },
    {
      label: "Delivers the required water",
      status: "Passed",
      note: "Meets the test's pressure and water-speed limits at the specified flow",
    },
    {
      label: "Saved design passes again",
      status: "Passed",
      note: "The saved building design file was checked again in a separate run",
    },
  ],
  monetarySavings: null,
  costNote:
    "Both options need 4.625 m of straight pipe. The simpler option removes four bends and eight connections between parts. That could reduce fitting and assembly costs; actual savings have not been priced.",
  assumptions:
    "The test uses idealized inside pipe dimensions, fixed water flow and specified resistance values for pipes and fittings. It compares only these two options.",
};

export const workflow = [
  {
    number: "01",
    title: "See what is in the building",
    text: "Bring the design files together to count equipment, pipes and connections.",
  },
  {
    number: "02",
    title: "Set the requirements",
    text: "Specify what each system must deliver, how much space it needs and which parts it can use.",
  },
  {
    number: "03",
    title: "Find where less can do the job",
    text: "Compare pipe lengths, fittings and performance to see what each option changes.",
  },
  {
    number: "04",
    title: "Save the design and check it again",
    text: "Check the saved design file and keep the results for review.",
  },
];

export const capabilities = [
  {
    id: "inventory",
    label: "See what is in the building",
    status: "Tested",
    text: "Equipment and connections counted across all seven hospital design files.",
  },
  {
    id: "routing",
    label: "Compare simpler pipe routes",
    status: "Tested",
    text: "Two example layouts compared for fit, connections and water delivery.",
  },
  {
    id: "export",
    label: "Save the changed design and check it again",
    status: "Tested",
    text: "The chosen pipe layout was saved as a building design file (IFC) and checked again.",
  },
  {
    id: "catalogues",
    label: "Calculate what each system needs",
    status: "Built",
    text: "Calculations for heating, cooling, water, drainage, electrical and fire systems using supplied design values.",
  },
  {
    id: "whole-building",
    label: "Improve every system in a building",
    status: "Still being developed",
    text: "A complete redesign of the hospital's connected systems has not been demonstrated.",
  },
];

export const demo = {
  label: "Try the demo",
  notice:
    "Explore recorded hospital results and try the pipe comparison. The demo uses saved results; it does not calculate a new building design.",
  viewerNotice:
    "Example building illustration · not the hospital's actual design",
  reportTitle: "OMA / ANANKE — Hospital demo results",
  releaseStatus: "Demo version",
};

export const evidence = {
  hospital,
  project,
  disciplines,
  routeComparison,
  workflow,
  capabilities,
  demo,
  provenance: {
    inventoryBuild:
      "b72cb24732b8b1d5ab08fdebda5e5649640a652b82bdda24a58f00d4da81b52c",
    routingBuild:
      "06aa865600b4ab2dc8f42f77b2cb5f82816dec99bbf8a1ff5f67673fb44c1949",
    inventoryReview:
      "A separate check confirmed the file counts and recorded connections",
    inventoryRegressionCases: 3426,
    inventoryDate: "2026-09-15",
    routeDate: "2026-09-15",
    dataType: "Saved test results",
  },
};

export default evidence;
