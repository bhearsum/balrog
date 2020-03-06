from flask import request

from ....services import releases
from .problem import problem


def get_releases():
    return releases.get_releases(request.transaction), 200


def update_release(name, body):
    if not releases.exists(name, request.transaction):
        return problem(404, "Missing", "Release does not exist")
    new_data_versions = releases.update_release(name, body["blob"], body["old_data_versions"], body.get("when"), request.username, request.transaction)
    return new_data_versions, 200


def set_release(name, body):
    new_data_versions = releases.set_release(
        name, body["blob"], body.get("product"), body.get("old_data_versions"), body.get("when"), request.username, request.transaction
    )
    return new_data_versions, 200
