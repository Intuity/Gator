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
import sys
from unittest.mock import MagicMock

import requests

import gator.parent
from gator.parent import _Parent
from gator.specs import Job

def test_parent_unlinked(mocker):
    """ By default, link will be False as no parent pointer """
    mocker.patch("os.environ")
    os.environ = {}
    assert not _Parent().linked

def test_parent_unlinked_calls(mocker):
    """ Unlinked parent should not attempt to make any calls to requests """
    mocker.patch("os.environ")
    mocker.patch("requests.get")
    mocker.patch("requests.post")
    os.environ = {}
    assert _Parent().spec("123") is None
    assert not requests.get.called
    assert not requests.post.called
    assert _Parent().register("123", "localhost:1234") is None
    assert not requests.get.called
    assert not requests.post.called
    assert _Parent().update("123", 234, 345) is None
    assert not requests.get.called
    assert not requests.post.called
    assert _Parent().complete("123", 0, 234, 345) is None
    assert not requests.get.called
    assert not requests.post.called

def test_parent_linked(mocker):
    """ If a parent pointer is set in the environment, link should be up """
    mocker.patch("os.environ")
    os.environ = { "GATOR_PARENT": "localhost:1234" }
    assert _Parent().linked

def test_parent_linked_calls(mocker):
    """ Linked parent should make requests to the parent server """
    mocker.patch("os.environ")
    mocker.patch("requests.get")
    mocker.patch("requests.post")
    os.environ = { "GATOR_PARENT": "localhost:1234" }
    # Check spec retrieval
    requests.get.return_value = MagicMock()
    requests.get.return_value.json.return_value = { "result": "success", "spec": "!Job:\nid: 123" }
    assert isinstance(_Parent().spec("123"), Job)
    requests.get.assert_called_with("http://localhost:1234/children/123")
    requests.get.reset_mock()
    assert not requests.post.called
    # Check child registration
    requests.post.return_value.json.return_value = { "result": "success" }
    assert _Parent().register("123", "localhost:2345") is None
    assert not requests.get.called
    requests.post.assert_called_with("http://localhost:1234/children/123",
                                     json={ "server": "localhost:2345" })
    requests.post.reset_mock()
    # Check child warning/error update
    requests.post.return_value.json.return_value = { "result": "success" }
    assert _Parent().update("123", 234, 345) is None
    assert not requests.get.called
    requests.post.assert_called_with("http://localhost:1234/children/123/update",
                                     json={ "warnings": 234, "errors": 345 })
    requests.post.reset_mock()
    # Check child completion
    requests.post.return_value.json.return_value = { "result": "success" }
    assert _Parent().complete("123", 0, 234, 345) is None
    assert not requests.get.called
    requests.post.assert_called_with("http://localhost:1234/children/123/complete",
                                     json={ "code": 0, "warnings": 234, "errors": 345 })
    requests.post.reset_mock()

def test_parent_failure(mocker):
    """ A message should be printed to STDERR if a parent GET/POST fails """
    mocker.patch("os.environ")
    mocker.patch("requests.get")
    mocker.patch("requests.post")
    mocker.patch("gator.parent.print")
    os.environ = { "GATOR_PARENT": "localhost:1234" }
    # Setup failure responses
    requests.get.return_value = MagicMock()
    requests.get.return_value.json.return_value = { "result": "failure" }
    requests.post.return_value = MagicMock()
    requests.post.return_value.json.return_value = { "result": "failure" }
    # Check spec retrieval
    _Parent().spec("123")
    requests.get.assert_called_with("http://localhost:1234/children/123")
    requests.get.reset_mock()
    assert not requests.post.called
    gator.parent.print.assert_called_with("Failed to GET from route 'children/123' via 'localhost:1234'",
                                          file=sys.stderr)
    gator.parent.print.reset_mock()
    # Check child registration
    _Parent().register("123", "localhost:2345")
    assert not requests.get.called
    requests.post.assert_called_with("http://localhost:1234/children/123",
                                     json={ "server": "localhost:2345" })
    requests.post.reset_mock()
    gator.parent.print.assert_called_with("Failed to POST to route 'children/123' via 'localhost:1234'",
                                          file=sys.stderr)
    gator.parent.print.reset_mock()
    # Check child warning/error update
    _Parent().update("123", 234, 345)
    assert not requests.get.called
    requests.post.assert_called_with("http://localhost:1234/children/123/update",
                                     json={ "warnings": 234, "errors": 345 })
    requests.post.reset_mock()
    gator.parent.print.assert_called_with("Failed to POST to route 'children/123/update' via 'localhost:1234'",
                                          file=sys.stderr)
    gator.parent.print.reset_mock()
    # Check child completion
    _Parent().complete("123", 0, 234, 345)
    assert not requests.get.called
    requests.post.assert_called_with("http://localhost:1234/children/123/complete",
                                     json={ "code": 0, "warnings": 234, "errors": 345 })
    requests.post.reset_mock()
    gator.parent.print.assert_called_with("Failed to POST to route 'children/123/complete' via 'localhost:1234'",
                                          file=sys.stderr)
    gator.parent.print.reset_mock()
