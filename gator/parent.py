# Copyright 2023, Peter Birch, mailto:peter@lightlogic.co.uk
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from pathlib import Path
from typing import Optional

from .common.api import API
from .specs import Spec

class _Parent(API):
    """ API wrapper to interface with the parent layer's server """

    ENV_VAR  = "GATOR_PARENT"
    CHILDREN = Path("children")

    def spec(self, id : str) -> Optional[Spec]:
        """
        Retrieve the Job or JobGroup specification for the provided child ID
        from the server.

        :param id:  Identifier of the child provided by the host layer
        :returns:   Either a Job, JobGroup, or None
        """
        if spec_str := self.get(self.CHILDREN / id).get("spec", None):
            return Spec.parse_str(spec_str)
        else:
            return None

    def register(self, id : str, server : str) -> None:
        """
        Register this instance with the host layer, providing the URI to this
        layer's server.

        :param id:      Identifier of this child provided by the host layer
        :param server:  Root URI of the server in this layer
        """
        self.post(self.CHILDREN / id, server=server)

    def update(self, id : str, warnings : int, errors : int) -> None:
        """
        Update the count of warnings and errors logged into this process by any
        children (processes or other layers).

        :param id:          Identifier of this child provided by the host layer
        :param warnings:    Number of warnings logged to this layer
        :param errors:      Number of errors logged to this layer
        """
        self.post(self.CHILDREN / id / "update", warnings=warnings, errors=errors)

    def complete(self, id : str, exit_code : int, warnings : int, errors : int) -> None:
        """
        Send the final counts of warnings and errors logged into this layer by
        any children (processes or other layers) and mark this stage done
        including its exit code.

        :param id:          Identifier of this child provided by the host layer
        :param exit_code:   Exit code collected by this layer
        :param warnings:    Number of warnings logged to this layer
        :param errors:      Number of errors logged to this layer
        """
        self.post(self.CHILDREN / id / "complete", code=exit_code, warnings=warnings, errors=errors)

Parent = _Parent()
