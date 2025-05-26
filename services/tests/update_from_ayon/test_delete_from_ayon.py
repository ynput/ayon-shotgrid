""" Test entity deletion from AYON to SG.
"""


def test_delete_folder(hub_and_project):
    mg = hub_and_project["mg"]
    project = hub_and_project["project"]
    hub = hub_and_project["hub"]

    # Création d'une séquence initiale
    mg.create("Sequence", {"project": project, "code": "my_sequence"})

    all_sequences = mg.find("Sequence", [["project", "is", project]])
    assert len(all_sequences) == 1

    # AYON event to fake the sequence delete
    ay_event = {
        'createdAt': '2025-04-29T17:02:17.951175+00:00',
        'dependsOn': None,
        'description': 'Folder my_new_episode deleted',
        'hash': 'b4ffe7d6251b11f0ac900242ac120002',
        'id': 'b4ffe7d6251b11f0ac900242ac120002',
        'payload': {
            'entityData': {
                'active': True,
                'attrib': {
                    'shotgridId': '1',
                    'shotgridType': 'Sequence'
                },
                'createdAt': '2025-04-29T14:10:34.591721+00:00',
                'data': {},
                'folderType': 'Sequence',
                'id': 'b6add2e0250311f08eedd9567d7d6404',
                'name': 'my_new_sequence',
                'path': '/my_new_sequence',
                'status': 'Not ready',
                'tags': [],
                'updatedAt': '2025-04-29T15:38:21.775660+00:00'
            }
        },
        'project': 'test_project',
        'retries': 0,
        'sender': '1YWHoUnmujGNUKwXWuiLvP',
        'senderType': 'api',
        'status': 'finished',
        'summary': {
            'entityId': 'b6add2e0250311f08eedd9567d7d6404',
            'parentId': None
        },
        'topic': 'entity.folder.deleted',
        'updatedAt': '2025-04-29T17:02:17.951175+00:00',
        'user': 'admin'
    }

    # Lancement de la réaction à l’événement de suppression
    hub.react_to_ayon_event(ay_event)

    # Vérifie que la séquence n'existe plus
    no_sequences = mg.find("Sequence", [["project", "is", project]])
    assert no_sequences == []
