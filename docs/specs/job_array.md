A `!JobArray` is similar to a [!JobGroup](job_group.md) in that it may contain
multiple [!Job](job.md) and [!JobGroup](job_group.md) instances, but unlike a
[!JobGroup](job_group.md) the child jobs are repeated a specified number of
times.

```yaml linenums="1"
!JobArray
  ident  : top
  repeats: 4
  cwd    : /path/to/working/directory
  env    :
    ENV_KEY_A: abcde
    ENV_KEY_B: 12345
  jobs   :
    - !Job
        ident  : echo_count
        command: echo
        args   :
          - "${GATOR_ARRAY_INDEX}"
    - ...
  on_done:
    - job_that_may_pass_or_fail
  on_pass:
    - job_that_must_pass
  on_fail:
    - job_that_will_fail
```

!!! note

    The `GATOR_ARRAY_INDEX` environment variable indexes which pass is currently
    being executed.

| Field       | Required         | Description                                                                       |
|-------------|:----------------:|-----------------------------------------------------------------------------------|
| `ident`     | :material-check: | Identifier for the job array, used to navigate job hierarchy                      |
| `repeats`   |                  | Number of times to repeat jobs in the list, defaults to 1                         |
| `cwd`       |                  | Working directory, if not specified then the launch shell's `$CWD` is used        |
| `env`       |                  | Dictionary of environment variables to overlay                                    |
| `jobs`      | :material-check: | [!Job](job.md), [!JobGroup](job_group.md), or `!JobArray` to repeatedly run       |
| `on_done`   |                  | List of other tasks that must complete (pass or fail) before launching this array |
| `on_pass`   |                  | List of other tasks that must succeed before launching this array                 |
| `on_fail`   |                  | List of other tasks that must fail before launching this array                    |

!!! note

    Dependencies specified in `on_done`, `on_pass`, and `on_fail` are
    ANDed together, such that all tasks listed must complete with the relevent
    pass or failure state before the dependent task is started.
