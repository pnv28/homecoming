"""Attach two ephemeral points while reusing the verified saved routing matrix.

Only the selected ordinary parent pieces are subdivided. The engine's original
attachment reuse, cost-profile checks, lift states, sparse minimum selection and
route reconstruction are retained; there is no whole-network recompilation.
"""
from collections import defaultdict
from types import SimpleNamespace
import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.sparse.csgraph import dijkstra

from estate_ranking.attachments import split_attachments
from estate_ranking.graph import PhysicalGraph,minimum_matrix
from estate_ranking.routes import path_transitions,ordered_sections,check_cost
from homecoming.services.coordinate import endpoint_attachments,empty_route
from homecoming.services.profiles import verified_profiles


def find_route(saved,start,end,evidence_directory):
    physical=saved.physical
    empty=gpd.GeoDataFrame(columns=['entity_id','status','geometry'],crs=2326)
    if start.equals(end):
        return dict(status='ok',message='Start and destination are the same coordinate.',
                    distance_m=0.,time_s=0.,route_cost_sum_verified=True),empty_route(),empty
    selected,_=endpoint_attachments(physical,start,end,saved.wheelchair)
    if len(selected)!=2 or not selected.status.eq('attached').all():
        return dict(status='unattached',message='No suitable permitted path within 200 m of one or both points.',
                    distance_m=None,time_s=None),empty_route(),selected
    parents=set(selected.parent_edge_index.astype(int))
    source_ids=set(selected.source_id)
    sources=(saved.source_loader(source_ids) if hasattr(saved,'source_loader') else
             physical.sources.loc[physical.sources.PedestrianRouteID.astype(str).isin(source_ids)].copy())
    local=PhysicalGraph(physical.nodes,physical.edges.loc[physical.edges.edge_index.isin(parents)].copy(),
        sources,
        physical.memberships.loc[physical.memberships.source_id.isin(source_ids)].copy(),
        physical.profiles,[],physical.policy)
    if evidence_directory is not None:
        local.profiles=verified_profiles(local,source_ids,evidence_directory)
    augmented,validation=split_attachments(local,selected,None)
    state_count=len(saved.states)
    by_node=defaultdict(list);base={}
    for row in saved.states.loc[saved.states.state_kind=='physical'].itertuples():
        node=int(row.node_index);by_node[node].append(int(row.state_index))
        if pd.isna(row.lift_id):base[node]=int(row.state_index)
    for node in range(len(physical.nodes),len(augmented.nodes)):
        base[node]=state_count;by_node[node]=[state_count];state_count+=1
    edge_offset=len(saved.edges)
    transitions=[]
    for edge in augmented.edges.itertuples():
        if not getattr(edge,'allow_wheelchair' if saved.wheelchair else 'allow_general'):
            continue
        if pd.notna(edge.lift_id):
            raise ValueError('Arbitrary endpoint subdivision must use an ordinary non-lift path.')
        for direction in (1,-1):
            if edge.direction not in (0,direction):continue
            cost=edge.time_forward_s if direction==1 else edge.time_reverse_s
            if pd.isna(cost) or not np.isfinite(cost):continue
            a,b=(int(edge.from_node),int(edge.to_node)) if direction==1 else (int(edge.to_node),int(edge.from_node))
            for source_state in by_node[a]:
                transitions.append((source_state,base[b],float(cost),edge_offset+int(edge.edge_index),direction,str(edge.source_id)))
    start_state,end_state=state_count,state_count+1
    for row in selected.itertuples():
        node=int(row.node_index)
        if row.role=='departure':
            transitions.append((start_state,base[node],float(row.time_s),-100000,1,row.attachment_id))
        else:
            for network_state in by_node[node]:
                transitions.append((network_state,end_state,float(row.time_s),-100001,1,row.attachment_id))
    kept=saved.transitions.loc[~saved.transitions.edge_index.isin(parents)]
    extra=pd.DataFrame(transitions,columns=kept.columns)
    matrix,mapping=minimum_matrix(pd.concat([kept,extra],ignore_index=True),state_count+2)
    graph=SimpleNamespace(matrix=matrix,transitions=mapping,
        edges=gpd.GeoDataFrame(pd.concat([saved.edges,augmented.edges],ignore_index=True),crs=2326),
        attachments=gpd.GeoDataFrame(pd.concat([saved.attachments,selected],ignore_index=True),crs=2326),
        metric='time',wheelchair=saved.wheelchair,scenario='primary')
    costs,predecessors=dijkstra(matrix,directed=True,indices=start_state,return_predecessors=True)
    if not np.isfinite(costs[end_state]):
        return dict(status='unreachable',message='Both points attached, but no permitted walking route connects them.',
                    distance_m=None,time_s=None),empty_route(),selected
    indices=path_transitions(graph,predecessors,start_state,end_state)
    route=ordered_sections(graph,indices,{'point:start':start,'point:end':end})
    check_cost(route.time_s,costs[end_state])
    return dict(status='ok',message='Fastest route under the saved walking model.',
                distance_m=float(route.distance_m.sum()),time_s=float(costs[end_state]),
                estimated_network_sections=int(route.uses_estimated_time.sum()),
                subdivision_validation=validation,route_cost_sum_verified=True),route,selected
