"""Check additive IFC relationships that can change original inverse facts."""


def added_relationship_effects(model, original_ids, new_part_ids, *, checked_void_id=None, separately_checked_original_ports=False):
    """Return forbidden inverse effects; STEP text preservation alone is weaker.

    Spatial containment of new parts is intentional. A named opening void and
    original terminal connections require their separate complete checkers.
    Neither allowance authenticates itself or grants geometric acceptance.
    """
    errors = []
    for relationship in model.by_type("IfcRelationship"):
        if relationship.id() in original_ids or relationship.id() == checked_void_id:
            continue
        originals = [e for e in model.traverse(relationship, max_levels=1)
                     if e.id() in original_ids and e.is_a("IfcObjectDefinition")]
        if not originals:
            continue
        if relationship.is_a() == "IfcRelContainedInSpatialStructure":
            valid = (len(originals) == 1 and originals[0] == relationship.RelatingStructure
                     and relationship.RelatingStructure.is_a("IfcSpatialStructureElement")
                     and bool(relationship.RelatedElements) and {e.id() for e in relationship.RelatedElements} <= new_part_ids)
        elif relationship.is_a() == "IfcRelConnectsPorts":
            valid = separately_checked_original_ports and all(e.is_a("IfcDistributionPort") for e in originals)
        else:
            valid = False
        if not valid:
            errors.append(f"Added relationship changes protected original inverse semantics: #{relationship.id()} {relationship.is_a()}")
    return errors
