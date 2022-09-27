from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

import pytest

from qcarchivetesting import load_molecule_data
from qcfractal.db_socket import SQLAlchemySocket
from qcportal.gridoptimization import GridoptimizationKeywords, GridoptimizationSpecification
from qcportal.optimization import OptimizationSpecification
from qcportal.record_models import RecordStatusEnum, PriorityEnum
from qcportal.singlepoint import QCSpecification
from .testing_helpers import compare_gridoptimization_specs, test_specs, submit_test_data, run_test_data

if TYPE_CHECKING:
    from qcfractal.db_socket import SQLAlchemySocket
    from qcportal import PortalClient
    from qcportal.managers import ManagerName


@pytest.mark.parametrize("tag", ["*", "tag99"])
@pytest.mark.parametrize("priority", list(PriorityEnum))
def test_gridoptimization_client_tag_priority(snowflake_client: PortalClient, tag: str, priority: PriorityEnum):
    peroxide2 = load_molecule_data("peroxide2")
    meta1, id1 = snowflake_client.add_gridoptimizations(
        [peroxide2],
        "gridoptimization",
        optimization_specification=OptimizationSpecification(
            program="geometric",
            qc_specification=QCSpecification(program="psi4", driver="deferred", method="hf", basis="sto-3g"),
        ),
        keywords=GridoptimizationKeywords(
            preoptimization=False,
            scans=[
                {"type": "distance", "indices": [1, 2], "steps": [-0.1, 0.0], "step_type": "relative"},
                {"type": "dihedral", "indices": [0, 1, 2, 3], "steps": [-90, 0], "step_type": "absolute"},
            ],
        ),
        priority=priority,
        tag=tag,
    )
    rec = snowflake_client.get_records(id1, include=["service"])
    assert rec[0].raw_data.service.tag == tag
    assert rec[0].raw_data.service.priority == priority


@pytest.mark.parametrize("spec", test_specs)
@pytest.mark.parametrize("owner_group", ["group1", None])
def test_gridoptimization_client_add_get(
    submitter_client: PortalClient, spec: GridoptimizationSpecification, owner_group: Optional[str]
):

    hooh = load_molecule_data("peroxide2")
    h3ns = load_molecule_data("go_H3NS")

    time_0 = datetime.utcnow()
    meta, id = submitter_client.add_gridoptimizations(
        [hooh, h3ns],
        spec.program,
        spec.optimization_specification,
        spec.keywords,
        tag="tag1",
        priority=PriorityEnum.low,
        owner_group=owner_group,
    )
    time_1 = datetime.utcnow()
    assert meta.success

    recs = submitter_client.get_gridoptimizations(id, include=["service", "initial_molecule"])
    assert len(recs) == 2

    for r in recs:
        assert r.record_type == "gridoptimization"
        assert r.raw_data.record_type == "gridoptimization"
        assert compare_gridoptimization_specs(spec, r.raw_data.specification)

        assert r.raw_data.service.tag == "tag1"
        assert r.raw_data.service.priority == PriorityEnum.low

        assert r.raw_data.owner_user == submitter_client.username
        assert r.raw_data.owner_group == owner_group

        assert time_0 < r.raw_data.created_on < time_1
        assert time_0 < r.raw_data.modified_on < time_1
        assert time_0 < r.raw_data.service.created_on < time_1

    assert recs[0].raw_data.initial_molecule.identifiers.molecule_hash == hooh.get_hash()
    assert recs[1].raw_data.initial_molecule.identifiers.molecule_hash == h3ns.get_hash()


def test_gridoptimization_client_add_existing_molecule(snowflake_client: PortalClient):
    spec = test_specs[0]

    mol1 = load_molecule_data("go_H3NS")
    mol2 = load_molecule_data("peroxide2")

    # Add a molecule separately
    _, mol_ids = snowflake_client.add_molecules([mol2])

    # Now add records
    meta, id = snowflake_client.add_gridoptimizations(
        [mol1, mol2, mol2, mol1],
        "gridoptimization",
        keywords=spec.keywords,
        optimization_specification=spec.optimization_specification,
        tag="tag1",
        priority=PriorityEnum.low,
    )

    assert meta.success
    assert meta.n_inserted == 2
    assert meta.n_existing == 2

    recs = snowflake_client.get_gridoptimizations(id, include=["initial_molecule"])
    assert len(recs) == 4
    assert recs[0].raw_data.id == recs[3].raw_data.id
    assert recs[1].raw_data.id == recs[2].raw_data.id

    rec_mols = {x.raw_data.initial_molecule.id for x in recs}
    _, mol_ids_2 = snowflake_client.add_molecules([mol1])
    assert rec_mols == set(mol_ids + mol_ids_2)


def test_gridoptimization_client_delete(
    snowflake_client: PortalClient, storage_socket: SQLAlchemySocket, activated_manager_name: ManagerName
):

    go_id = run_test_data(storage_socket, activated_manager_name, "go_H2O2_psi4_pbe")

    rec = storage_socket.records.gridoptimization.get([go_id], include=["optimizations"])
    child_ids = [x["optimization_id"] for x in rec[0]["optimizations"]]

    meta = snowflake_client.delete_records(go_id, soft_delete=True, delete_children=False)
    assert meta.success
    assert meta.deleted_idx == [0]
    assert meta.n_children_deleted == 0

    child_recs = snowflake_client.get_records(child_ids, missing_ok=True)
    assert all(x.status == RecordStatusEnum.complete for x in child_recs)

    snowflake_client.undelete_records(go_id)

    meta = snowflake_client.delete_records(go_id, soft_delete=True, delete_children=True)
    assert meta.success
    assert meta.deleted_idx == [0]
    assert meta.n_children_deleted == len(child_ids)

    child_recs = snowflake_client.get_records(child_ids, missing_ok=True)
    assert all(x.status == RecordStatusEnum.deleted for x in child_recs)

    meta = snowflake_client.delete_records(go_id, soft_delete=False, delete_children=True)
    assert meta.success
    assert meta.deleted_idx == [0]
    assert meta.n_children_deleted == len(child_ids)

    recs = snowflake_client.get_gridoptimizations(go_id, missing_ok=True)
    assert recs is None

    child_recs = snowflake_client.get_records(child_ids, missing_ok=True)
    assert all(x is None for x in child_recs)

    # DB should be pretty empty now
    query_res = snowflake_client.query_records()
    assert query_res.current_meta.n_found == 0


def test_gridoptimization_client_harddelete_nochildren(
    snowflake_client: PortalClient, storage_socket: SQLAlchemySocket, activated_manager_name: ManagerName
):

    go_id = run_test_data(storage_socket, activated_manager_name, "go_H2O2_psi4_pbe")

    rec = storage_socket.records.gridoptimization.get([go_id], include=["optimizations"])
    child_ids = [x["optimization_id"] for x in rec[0]["optimizations"]]

    meta = snowflake_client.delete_records(go_id, soft_delete=False, delete_children=False)
    assert meta.success
    assert meta.deleted_idx == [0]
    assert meta.n_children_deleted == 0

    recs = snowflake_client.get_gridoptimizations(go_id, missing_ok=True)
    assert recs is None

    child_recs = snowflake_client.get_records(child_ids, missing_ok=True)
    assert all(x is not None for x in child_recs)


def test_gridoptimization_client_delete_opt_inuse(
    snowflake_client: PortalClient, storage_socket: SQLAlchemySocket, activated_manager_name: ManagerName
):

    go_id = run_test_data(storage_socket, activated_manager_name, "go_H2O2_psi4_pbe")

    rec = storage_socket.records.gridoptimization.get([go_id], include=["optimizations"])
    child_ids = [x["optimization_id"] for x in rec[0]["optimizations"]]

    meta = snowflake_client.delete_records(child_ids[0], soft_delete=False)
    assert meta.success is False
    assert meta.error_idx == [0]

    ch_rec = snowflake_client.get_records(child_ids[0])
    assert ch_rec is not None


def test_gridoptimization_client_query(snowflake_client: PortalClient, storage_socket: SQLAlchemySocket):
    id_1, _ = submit_test_data(storage_socket, "go_H2O2_psi4_b3lyp")
    id_2, _ = submit_test_data(storage_socket, "go_H2O2_psi4_pbe")
    id_3, _ = submit_test_data(storage_socket, "go_C4H4N2OS_psi4_b3lyp-d3bj")
    id_4, _ = submit_test_data(storage_socket, "go_H3NS_psi4_pbe")

    all_gos = snowflake_client.get_gridoptimizations([id_1, id_2, id_3, id_4])
    mol_ids = [x.initial_molecule_id for x in all_gos]

    query_res = snowflake_client.query_gridoptimizations(qc_program=["psi4"])
    assert query_res.current_meta.n_found == 4

    query_res = snowflake_client.query_gridoptimizations(qc_program=["nothing"])
    assert query_res.current_meta.n_found == 0

    query_res = snowflake_client.query_gridoptimizations(initial_molecule_id=[mol_ids[0], 9999])
    assert query_res.current_meta.n_found == 2

    # query for optimization program
    query_res = snowflake_client.query_gridoptimizations(optimization_program=["geometric"])
    assert query_res.current_meta.n_found == 4

    # query for optimization program
    query_res = snowflake_client.query_gridoptimizations(optimization_program=["geometric123"])
    assert query_res.current_meta.n_found == 0

    # query for basis
    query_res = snowflake_client.query_gridoptimizations(qc_basis=["sTO-3g"])
    assert query_res.current_meta.n_found == 3

    query_res = snowflake_client.query_gridoptimizations(qc_basis=[None])
    assert query_res.current_meta.n_found == 0

    query_res = snowflake_client.query_gridoptimizations(qc_basis=[""])
    assert query_res.current_meta.n_found == 0

    # query for method
    query_res = snowflake_client.query_gridoptimizations(qc_method=["b3lyP"])
    assert query_res.current_meta.n_found == 1

    # Query by default returns everything
    query_res = snowflake_client.query_gridoptimizations()
    assert query_res.current_meta.n_found == 4

    # Query by default (with a limit)
    query_res = snowflake_client.query_gridoptimizations(limit=1)
    assert query_res.current_meta.n_found == 4
