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

from unittest.mock import MagicMock

import pytest

import gator.server
from gator.server import Server

@pytest.fixture()
def server():
    server = Server(db=MagicMock())
    server.app.config.update({ "TESTING": True })
    yield server

@pytest.fixture()
def client(server):
    return server.app.test_client()

def test_server_root(client):
    """ GET request to '/' should return the tool identification """
    response = client.get("/")
    assert response.status_code == 200
    assert response.json == { "tool": "gator", "version": "1.0" }

def test_server_log(server, client):
    """ POST request to '/' should trigger a log message """
    for idx, sev in enumerate(("DEBUG", "INFO", "WARNING", "ERROR")):
        response = client.post("/log", json={ "timestamp": 123 * (idx + 1),
                                              "severity" : sev,
                                              "message"  : f"Hello world {idx}" })
        assert response.status_code == 200
        assert response.json == { "result": "success" }
        server.db.push_log.assert_called_with(sev, f"Hello world {idx}", 123 * (idx + 1))

def test_server_unsupported(client):
    """ Check non-existent GET and POST routes return an error """
    # 405: Method Not Allowed
    assert client.get("/log").status_code == 405
    assert client.post("/").status_code == 405
    # 404: Not Found
    assert client.get("/blah123").status_code == 404
    assert client.post("/blah123").status_code == 404

def test_server_port_address(server, mocker):
    """ Check that port and address are returned """
    mocker.patch("gator.server.socket")
    gator.server.socket.gethostname.return_value = "test_server_abc"
    server._Server__port = 12345
    assert server.port == 12345
    assert server.address == "test_server_abc:12345"

def test_server_port_db_preserved():
    """ Check that the port and database objects are stored """
    server = Server(port=12345, db=(db := MagicMock()))
    assert server.port == 12345
    assert server.db is db

def test_server_port_locking(mocker):
    """ Check that locks are requested in the right order """
    mocker.patch("gator.server.Lock")
    mocker.patch("gator.server.Flask")
    mocker.patch("gator.server.logging")
    lock_inst = MagicMock()
    gator.server.Lock.return_value = lock_inst
    # Creating the server should create and request a lock
    server = Server()
    assert lock_inst.acquire.called
    lock_inst.acquire.reset_mock()
    # Requesting the port should attempt to acquire and then release the lock
    assert server.port is None
    assert lock_inst.acquire.called
    assert lock_inst.release.called
    lock_inst.acquire.reset_mock()
    lock_inst.release.reset_mock()
    # Starting the server should release the lock
    server.start()
    assert server.thread is not None
    server.thread.join()
    assert lock_inst.release.called
    lock_inst.release.reset_mock()
    assert server.port is not None

def test_server_port_explicit(mocker):
    """ Check that a specifically requested port is preserved """
    mocker.patch("gator.server.Lock")
    mocker.patch("gator.server.Flask")
    mocker.patch("gator.server.logging")
    server = Server(port=12345)
    server.start()
    server.thread.join()
    assert server.port == 12345

def test_server_custom_get_route(server):
    """ Check that a custom GET route works """
    # Register a GET route
    cb = MagicMock()
    cb.__name__ = "testroute"
    cb.return_value = { "message": "hello world" }
    server.register_get("/testroute", cb)
    # Register a GET route with a parameter
    cb_prm = MagicMock()
    cb_prm.__name__ = "testparam"
    cb_prm.return_value = { "message": "goodbye" }
    server.register_get("/testparam/<hello>", cb_prm)
    # Test the basic route
    response = server.app.test_client().get("/testroute")
    assert response.status_code == 200
    assert response.json == { "message": "hello world" }
    assert cb.called
    # Test the parameterised route
    response = server.app.test_client().get("/testparam/fred")
    assert response.status_code == 200
    assert response.json == { "message": "goodbye" }
    cb_prm.assert_called_with(hello="fred")

def test_server_custom_post_route(server):
    """ Check that a custom POST route works """
    # Register a POST route
    cb = MagicMock()
    cb.__name__ = "testroute"
    cb.return_value = { "message": "hello world" }
    server.register_post("/testroute", cb)
    # Register a POST route with a parameter
    cb_prm = MagicMock()
    cb_prm.__name__ = "testparam"
    cb_prm.return_value = { "message": "goodbye" }
    server.register_post("/testparam/<hello>", cb_prm)
    # Test the basic route
    response = server.app.test_client().post("/testroute", json={"message": "greetings"})
    assert response.status_code == 200
    assert response.json == { "message": "hello world" }
    assert cb.called
    # Test the parameterised route
    response = server.app.test_client().post("/testparam/fred", json={"message": "greetings"})
    assert response.status_code == 200
    assert response.json == { "message": "goodbye" }
    cb_prm.assert_called_with(hello="fred")
