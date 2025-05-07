""" Tests for services code.
"""
import os
import sys

from shotgun_api3.lib import mockgun


# Setup mockgun with default Flow/Shotgrid schemas
_current_dir = os.path.dirname(__file__)
_resources_dir = os.path.join(_current_dir, "resources")
mockgun.Shotgun.set_schema_paths(
    os.path.join(_resources_dir, "basic_sg_schema"),
    os.path.join(_resources_dir, "basic_sg_entity_schema"),
)


# hack "service" is not a proper python package
sys.path.append(os.path.join(_current_dir, "..", "shotgrid_common"))
