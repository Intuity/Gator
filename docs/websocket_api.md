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

The request fields of this action are as follows:

| Field     | Required         | Type    | Description                                                                                 |
|-----------|:----------------:|---------|---------------------------------------------------------------------------------------------|
| timestamp |                  | integer | Unix timestamp when the message was created (defaults to the current time)                  |
| severity  |                  | string  | Logging severity must be one of DEBUG, INFO, WARNING, ERROR, or CRITICAL (defaults to INFO) |
| message   | :material-check: | string  | The message to log                                                                          |

!!! note

    It is recommended to set `posted` to `true` for the `log` action as this will
    reduce load on both the client and server in cases of high message throughput.

### Stop

The `stop` action terminates a job running within a wrapper and is distributed
by tiers to all child tiers and wrappers, also stopping any further tasks from
being scheduled. It propagates downwards through the tier and wrapper hierarchy.
An example of a `stop` request is as follows:

```json
{
    "action" : "stop",
    "req_id" : 1,
    "posted" : false,
    "payload": {}
}
```

This action requires no payload to be provided and can sent either posted or
non-posted, in which case a response with an empty payload will be emitted once
the stop requested has been forwarded on to all children (but jobs may still be
in the process of being terminated).

## Tier Actions

This section includes actions specific to a [tier](./how_it_works.md).

### Children

The `children` action lists all of the immediate children of a given tier, their
current state and any metrics they have reported.

=== "Request"

    ```json
    {
        "action" : "children",
        "req_id" : 1,
        "posted" : false,
        "payload": {}
    }
    ```

=== "Response"

    ```json
    {
        "action" : "children",
        "rsp_id" : 1,
        "result" : "success",
        "payload": {
            "child_a": {
                "state"    : "STARTED",
                "result"   : "UNKNOWN",
                "server"   : "192.168.0.123:12356",
                "metrics"  : { "msg_debug": 10, "msg_info": 4, "lint_warnings": 123 },
                "exitcode" : 0,
                "started"  : 1684696100,
                "updated"  : 1684696137,
                "completed": 0
            },
            ...
        }
    }
    ```

The response payload contains a dictionary of every known child ID along with
its current status. The status of each child will contain the following fields.

| Field     | Type    | Description                                                                              |
|-----------|---------|------------------------------------------------------------------------------------------|
| state     | string  | Current status of the job which will be `PENDING`, `LAUNCHED`, `STARTED`, or `COMPLETE`  |
| result    | string  | Result of the job once it has completed which will be `UNKNOWN`, `SUCCESS`, or `FAILURE` |
| server    | string  | URL of the websocket server running within the tier or wrapper                           |
| metrics   | dict    | Dictionary of metrics aggregated by the tier or wrapper                                  |
| exitcode  | integer | Exit code of the job running within a wrapper layer, set once complete                   |
| started   | integer | Unix timestamp when the child started                                                    |
| updated   | integer | Unix timestamp of the last update received from the child                                |
| completed | integer | Unix timestamp when the child completed                                                  |

### Get Tree

The `get_tree` action returns a dictionary containing a snapshot of the tree of
active jobs, recursively gathered by querying each tier.

=== "Request"

    ```json
    {
        "action" : "get_tree",
        "req_id" : 1,
        "posted" : false,
        "payload": {}
    }
    ```

=== "Response"

    ```json
    {
        "action" : "get_tree",
        "rsp_id" : 1,
        "result" : "success",
        "payload": {
            "root_group": {
                "child_group": {
                    "grandchild_job_a": "STARTED",
                    "grandchild_job_b": "PENDING"
                },
                "child_job": "COMPLETE"
            }
        }
    }
    ```

The response payload carries a tree where each key is the name of a tier or
wrapper, with the leaf node values carrying the state of specific job wrappers
(either `PENDING`, `LAUNCHED`, `STARTED`, or `COMPLETE`).

### Spec

The `spec` endpoint is used by child tiers and wrappers to retrieve the work
specification to execute.

=== "Request"

    ```json
    {
        "action" : "spec",
        "req_id" : 1,
        "posted" : false,
        "payload": {
            "ident": "child_job_a"
        }
    }
    ```

=== "Response"

    ```json
    {
        "action" : "get_tree",
        "rsp_id" : 1,
        "result" : "success",
        "payload": {
            "spec": "!Job\nident: child_job_a\n..."
        }
    }
    ```

The request fields of this action are as follows:

| Field | Required         | Type    | Description                             |
|-------|:----------------:|---------|-----------------------------------------|
| ident | :material-check: | string  | Identifier of the child tier or wrapper |

The response fields of this action are as follows:

| Field | Type    | Description                                                   |
|-------|---------|---------------------------------------------------------------|
| spec  | string  | Uncompressed YAML work specification for this tier or wrapper |

### Register

When child tiers and wrappers are launched, the parent tier changes their state
to `LAUNCHED`. When the child is scheduled, it connects to the parent's websocket
and sends the `register` action which updates its state to `STARTED`.

=== "Request"

    ```json
    {
        "action" : "register",
        "req_id" : 1,
        "posted" : false,
        "payload": {
            "ident" : "child_job_a",
            "server": "192.168.0.65:54241"
        }
    }
    ```

=== "Response"

    ```json
    {
        "action" : "register",
        "rsp_id" : 1,
        "result" : "success",
        "payload": {}
    }
    ```

The request fields of this action are as follows:

| Field  | Required         | Type    | Description                             |
|--------|:----------------:|---------|-----------------------------------------|
| ident  | :material-check: | string  | Identifier of the child tier or wrapper |
| server | :material-check: | string  | URL of the child's websocket            |

### Update

While a child tier or wrapper is running, it should provide periodic updates to
the parent tier, this is known as the 'heartbeat'. These updates are provided
via the `update` action.

=== "Request"

    ```json
    {
        "action" : "update",
        "req_id" : 1,
        "posted" : false,
        "payload": {
            "ident"     : "child_a",
            "metrics"   : {
                "sub_total" : 10,
                "sub_active": 4,
                "sub_passed": 2,
                "sub_failed": 1,
                "msg_debug"    : 3,
                "msg_info"     : 5,
                "msg_warning"  : 2,
                "msg_error"    : 3,
                "msg_critical" : 0,
                "lint_warnings": 123
            }
        }
    }
    ```

=== "Response"

    ```json
    {
        "action" : "update",
        "rsp_id" : 1,
        "result" : "success",
        "payload": {}
    }
    ```

The request fields of this action are as follows:

| Field      | Required         | Type    | Description                                                           |
|------------|:----------------:|---------|-----------------------------------------------------------------------|
| ident      | :material-check: | string  | Identifier of the child tier or wrapper                               |
| sub_total  | :material-check: | integer | Number of total jobs expected to run at or beneath the child layer    |
| sub_active | :material-check: | integer | Number of currently active jobs running at or beneath the child layer |
| sub_passed | :material-check: | integer | Number of jobs completed successful at or beneath the child layer     |
| sub_failed | :material-check: | integer | Number of jobs that have failed at or beneath the child layer         |
| metrics    | :material-check: | dict    | Dictionary of metric values aggregated to this layer                  |

!!! note

    In many cases it may be best to send `update` actions with the `posted` field
    set to `true` to lower the amount of communication from the parent to the
    child. However, using non-posted requests is a useful way of determining that
    the parent tier is still alive.

### Complete

While a child tier or wrapper is completes, it should send a final status update
to the parent tier using the `complete` action.

=== "Request"

    ```json
    {
        "action" : "complete",
        "req_id" : 1,
        "posted" : false,
        "payload": {
            "ident"     : "child_a",
            "result"    : "SUCCESS",
            "code"      : 0,
            "metrics"   : {
                "sub_total" : 10,
                "sub_passed": 2,
                "sub_failed": 1,
                "msg_debug"    : 3,
                "msg_info"     : 5,
                "msg_warning"  : 2,
                "msg_error"    : 3,
                "msg_critical" : 0,
                "lint_warnings": 123
            }
        }
    }
    ```

=== "Response"

    ```json
    {
        "action" : "complete",
        "rsp_id" : 1,
        "result" : "success",
        "payload": {}
    }
    ```

The request fields of this action are as follows:

| Field      | Required         | Type    | Description                                                        |
|------------|:----------------:|---------|--------------------------------------------------------------------|
| ident      | :material-check: | string  | Identifier of the child tier or wrapper                            |
| result     | :material-check: | string  | Child's result either `SUCCESS` or `FAILURE`                       |
| code       | :material-check: | integer | Exit code of the child wrapper's task                              |
| sub_total  | :material-check: | integer | Number of total jobs expected to run at or beneath the child layer |
| sub_passed | :material-check: | integer | Number of jobs completed successful at or beneath the child layer  |
| sub_failed | :material-check: | integer | Number of jobs that have failed at or beneath the child layer      |
| metrics    | :material-check: | dict    | Dictionary of metric values aggregated to this layer               |

## Wrapper Actions

This section includes actions specific to a [wrapper](./how_it_works.md).

### Metric

The `metric` action allows an arbitrary numerical value to be reported into the
Gator metrics engine. It is only passed from the task running within the wrapper
to the wrapper itself, it does not directly propagate further up the tree.
An example of a `metric` request is shown below:

```json
{
    "action" : "metric",
    "req_id" : 1,
    "posted" : true,
    "payload": {
        "name" : "lint_warnings",
        "value": 132
    }
}
```

The request fields of this action are as follows:

| Field | Required         | Type    | Description                  |
|-------|:----------------:|---------|------------------------------|
| name  | :material-check: | string  | Name of the metric to record |
| value | :material-check: | integer | Value of the metric          |

!!! note

    The same metric value can be recorded multiple times but only the final value
    recorded will be preserved.
