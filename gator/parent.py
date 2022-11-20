import os

import requests

class _Parent:

    def __init__(self):
        self.parent = os.environ.get("GATOR_PARENT", None)

    @property
    def linked(self):
        return self.parent is not None

    def post(self, route, **kwargs):
        if self.linked:
            resp = requests.post(f"http://{self.parent}/{route}", json=kwargs)
            data = resp.json()
            if data.get("result", None) != "success":
                print(f"Failed to post to route '{route}' via '{self.parent}'")
            return data
        else:
            return {}

    def register(self, id, server):
        self.post(f"children/{id}", server=server)

    def complete(self, id, exit_code, warnings, errors):
        self.post(f"children/{id}/complete", code=exit_code, warnings=warnings, errors=errors)

    def update(self, id, warnings, errors):
        self.post(f"children/{id}/update", warnings=warnings, errors=errors)

Parent = _Parent()
