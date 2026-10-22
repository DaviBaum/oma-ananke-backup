from itertools import combinations
import copy
import math

import ifcopenshell
import pytest

from oma.ifc.audit import sha256_file
from oma.ifc.network import export_network,check_network_semantics
from oma.ifc.cad import cad_check_routes
from native_three_sink_fixture import make_original,three_sink_spec,complete_native_evidence


@pytest.mark.parametrize('millimeters',[False,True])
def test_actual_two_tee_three_sink_full_native_denominators(tmp_path,millimeters):
    source=make_original(tmp_path/'original.ifc',millimeters=millimeters)
    evidence=complete_native_evidence(source,tmp_path/'network.ifc')
    semantic,cad=evidence['semantics'],evidence['cad']
    assert semantic['status']=='PASS',semantic['errors']
    assert (semantic['physical_components'],semantic['physical_ports'],semantic['connections'])==(7,16,6)
    assert semantic['unique_length_m']==pytest.approx(6.)
    assert semantic['demand_path_lengths_m']==pytest.approx({'demand-a':2.,'demand-b':4.,'demand-c':4.})
    tees=[p for p in semantic['parts'] if p['kind']=='tee']
    assert len(tees)==2 and len({p['ifc_guid'] for p in tees})==2
    assert all(p['native_solid_count']==1 for p in semantic['parts'])
    assert all(p['native_volume_m3']==pytest.approx(math.pi*.07**2*.6-8*.07**3/3,abs=1e-9) for p in tees)
    assert all(p['status']=='PASS' and p['owner_placement_status']=='OWNER_RELATIVE' for p in semantic['ports'])
    assert cad['coordination_status']==cad['self_interference_status']=='PASS'
    assert (cad['route_count'],cad['obstacle_count'],cad['pairs_accounted'])==(7,1,7)
    pairs=cad['self_pair_results']
    assert len(pairs)==21 and {frozenset(x['participant_guids']) for x in pairs}=={frozenset(x) for x in combinations(cad['route_guids'],2)}
    assert sum(x['reason']=='ZERO_VOLUME_CONTACT_CONFINED_TO_EXPLICIT_JOINT_DISK' for x in pairs)==6
    assert evidence['zone']['status']=='PASS' and len(evidence['native_connection_signs'])==6
    assert evidence['source_unchanged'] and evidence['manifest']['original_records_changed']==[]


@pytest.mark.parametrize('damage',['second_tee_axis','second_tee_union','duplicate_tee_identity','reverse_second_connection'])
def test_second_tee_cannot_disappear_or_use_invalid_cap_semantics(tmp_path,damage):
    source=make_original(tmp_path/'source.ifc');output=tmp_path/'network.ifc'
    manifest=export_network(source,output,three_sink_spec())
    model=ifcopenshell.open(str(output))
    tee=next(p for p in manifest['added_parts'] if p['component_id']=='tee-2')
    if damage=='second_tee_axis':model.by_guid(tee['ports']['branch']).ObjectPlacement.RelativePlacement.Axis.DirectionRatios=[0.,-1.,0.]
    elif damage=='second_tee_union':model.by_guid(tee['ifc_guid']).Representation.Representations[0].Items[0].Operator='DIFFERENCE'
    elif damage=='duplicate_tee_identity':tee['ifc_guid']=next(p['ifc_guid'] for p in manifest['added_parts'] if p['component_id']=='tee-1')
    else:
        relation=next(r for r in model.by_type('IfcRelConnectsPorts') if r.RelatedPort.GlobalId==tee['ports']['a'])
        relation.RelatingPort,relation.RelatedPort=relation.RelatedPort,relation.RelatingPort
    model.write(str(output));manifest['export_sha256']=sha256_file(output)
    result=check_network_semantics(output,source,manifest)
    assert result['status']=='FAIL' and result['errors']


def test_additional_original_obstacle_is_in_full_two_tee_denominator(tmp_path):
    source=make_original(tmp_path/'source.ifc',blocking=True)
    output=tmp_path/'network.ifc';manifest=export_network(source,output,three_sink_spec())
    cad=cad_check_routes([source],output,[p['ifc_guid'] for p in manifest['added_parts']],clearance_m=.1)
    assert cad['coordination_status']=='FAIL' and cad['failed_pairs']>0
    assert (cad['route_count'],cad['obstacle_count'],cad['pairs_accounted'])==(7,2,14)
    assert cad['self_interference_status']=='PASS' and len(cad['self_pair_results'])==21
    assert sha256_file(source)==manifest['source_sha256']
