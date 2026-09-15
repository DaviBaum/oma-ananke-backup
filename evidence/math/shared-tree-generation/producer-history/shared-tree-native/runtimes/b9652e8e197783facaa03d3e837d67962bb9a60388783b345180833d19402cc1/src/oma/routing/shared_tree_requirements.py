"""Shared field-level parser; complete generated designs still need mission validation."""
from copy import deepcopy
from pydantic import create_model
from oma.models import Model
from oma.routing.network_scenario import SharedNetworkScenario

# Copy FieldInfo so parser construction cannot mutate the existing mission model.
# Its numeric coercion/default/section/physics semantics remain the existing API's.
SharedTreeRequirements = create_model('SharedTreeRequirements', __base__=Model,
    **{name:(field.annotation,deepcopy(field)) for name,field in SharedNetworkScenario.model_fields.items()
       if name!='network_alternatives'})


def normalize_shared_tree_requirements(raw):
    return SharedTreeRequirements.model_validate(raw).model_dump(mode='json',by_alias=True)
