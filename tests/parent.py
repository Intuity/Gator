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

import os

from gator.parent import _Parent

def test_parent_linked(mocker):
    mocker.patch("os.environ")
    os.environ = {}
    # By default, link will be False as no parent pointer
    assert not _Parent().linked
    # If a parent pointer is set in the environment, link should be up
    os.environ = { "GATOR_PARENT": "localhost:1234" }
    assert _Parent().linked
