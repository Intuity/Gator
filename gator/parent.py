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
            print(f"Post to '{route}': {kwargs}")
            return {}

    def register(self, id, server):
        self.post("child", id=id, server=server)

    def complete(self, id, exit_code, warnings, errors):
        self.post("child/complete", id=id, code=exit_code, warnings=warnings, errors=errors)

    def update(self, id, warnings, errors):
        self.post("child/update", id=id, warnings=warnings, errors=errors)

Parent = _Parent()
