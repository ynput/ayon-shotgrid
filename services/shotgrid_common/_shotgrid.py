""" Flow/Shotgrid API wrapper.
"""
from typing import Optional, Dict, List

import shotgun_api3

_SG = None


def _get_valid_sg_connection(
        sg: Optional[object] = None,
    ):
    """
    """
    if isinstance(sg, shotgun_api3.Shotgun) and sg.connect():
        return sg

    if isinstance(sg, shotgun_api3.lib.mockgun.Shotgun):
        return sg  # mockgun == test framework

    if sg:
        raise RuntimeError(
            f"Invalid connection provided: {sg}."
        )

#    elif _SG is None:
#        _SG = shotgun_api3.Shotgun(
#            self.sg_url,
#            script_name=self.sg_script_name,
#            api_key=self.sg_api_key
#        )

    return _SG


def get_entity(
        entity_type: str,
        entity_id: int,
        project_id: Optional[int] = None,
        allow_none: Optional[bool] = False,
        fields: Optional[List[str]] = None,
        sg: Optional[object] = None
    ) -> Dict:
    """
    """
    sg = _get_valid_sg_connection(sg)

    filters = [["id", "is", entity_id]]
    if project_id:
        filters.append(["project.Project.id", "is", project_id])

    result = sg.find_one(
        entity_type,
        filters=filters,
        fields=fields,
    )

    if not result and not allow_none:
        error_msg = f"Cannot find entity id: {entity_id} of type {entity_type}"
        if project_id:
            error_msg += f" under project id {project_id}"

        raise ValueError(error_msg)

    return result


def get_all_entities(
        entity_type: str,
        project_id: int,
        fields: Optional[List[str]] = None,
        sg: Optional[object] = None,
    ):
    """
    """
    sg = _get_valid_sg_connection(sg)

    return sg.find(
        entity_type,
        filters=[["project.Project.id", "is", project_id]],
        fields=fields,
    )
