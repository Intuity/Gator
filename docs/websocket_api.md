Gator uses websockets to communicate between the [tiers and wrappers](./how_it_works.md)
executing a given work specification. Tasks running within a wrapper can communicate
with it to log messages and record metrics using this API, and data is aggregated
during regular heartbeat intervals and whenever a tier or wrapper completes.

Communication through websockets is bi-directional, so messages can also travel
down through the hierarchy to perform operations like discovering the active
tree or stopping all jobs currently running.

## Basic Format

All messages travelling over Gator's websocket connections are encoded in JSON,
while this is not necessarily the most efficient way to serialize data it was
chosen for its widely available support across many languages without installing
additional packages.

=== "Request Format"

    ```json
    {
        "action" : "some_action",
        "req_id" : 23,
        "posted" : false,
        "payload": {
            "key_a": "value_a",
            "key_b": 987
        }
    }
    ```

    !!! warning

        If the `posted` attribute is set to `true` then the host will silently
        consume the message and will not emit a response unless the message fails
        to be decoded.

=== "Successful Response Format"

    ```json
    {
        "action" : "some_action",
        "rsp_id" : 23,
        "result" : "success",
        "payload": {
            "key_c": true,
            "key_d": "value_d"
        }
    }
    ```

=== "Failure Response Format"

    ```json
    {
        "result": "error",
        "rsp_id": 23,
        "reason": "An explanation of the error"
    }
    ```

!!! info

    If an identifier (`req_id`) is provided in the request then it will always
    be copied into the response (`rsp_id`) allowing multiple outstanding messages
    to be sent to the host before responses are emitted.

## Common Actions

Tiers and wrappers both support the actions listed in this section.

### Log

The `log` action allows messages to be recorded into the SQLite database of a
job's wrapper, or forwarded to the console. It propagates upwards through the
wrapper and tier hierarchy. An example of a `log` request is as follows:

```json
{
    "action" : "log",
    "req_id" : 1,
    "posted" : true,
    "payload": {
        "timestamp": 1684696137,
        "severity" : "WARNING",
        "message"  : "This is a warning message"
    }
}
```

The fields of this action are as follows:

| Field     | Required         | Description                                                                                 |
|-----------|:----------------:|---------------------------------------------------------------------------------------------|
| timestamp |                  | Unix timestamp when the message was created (defaults to the current time)                  |
| severity  |                  | Logging severity must be one of DEBUG, INFO, WARNING, ERROR, or CRITICAL (defaults to INFO) |
| message   | :material-check: | The message to log                                                                          |

!!! note

    It is recommended to set `posted` to `true` for the `log` action as this will
    reduce load on both the client and server in cases of high message throughput.

### Stop

The `stop` action terminates a job running within a wrapper and is distributed
by tiers to all child tiers and wrappers, also stopping any further tasks from
being scheduled. An example of a `stop` request is as follows:

```json
{
    "action" : "stop",
    "req_id" : 1,
    "posted" : false,
    "payload": {}
}
```

This action requires no payload to be provided and can sent either posted or
non-posted, in which case a response is emitted once the stop requested has been
forwarded on to all children (but jobs may still be in the process of being
terminated).
