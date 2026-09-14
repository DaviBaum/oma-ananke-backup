import type { Entity } from "./types";
export function isServiceElement(entity: Entity) {
  return /^(IfcFlow|IfcPipe|IfcDuct|IfcCable|IfcAirTerminal|IfcUnitary|IfcPump|IfcFan|IfcBoiler|IfcChiller|IfcCoil|IfcHeatExchanger|IfcValve|IfcDamper|IfcFireSuppressionTerminal|IfcSanitaryTerminal|IfcElectrical|IfcElectric|IfcProtectiveDevice|IfcJunctionBox|IfcLightFixture|PhysicalRoute)/.test(
    entity.ifc_type ?? "",
  );
}
