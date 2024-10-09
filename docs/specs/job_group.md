A `!JobGroup` can specify a collection of jobs to be executed by Gator, each
grouping can contain instances of [!Job](job.md), [!JobArray](job_array.md),
and nested `!JobGroup` layers:

```yaml linenums="1"
!JobGroup
  ident  : top
  cwd    : /path/to/working/directory
  env    :
    ENV_KEY_A: abcde
    ENV_KEY_B: 12345
  jobs   :
    - !Job
        ident  : job_a
        command: echo
        args   :
         - "This is job A"
    - !JobGroup
        ident: inner
        jobs:
          - !Job
            ident  : job_b
            command: echo
            args   :
              - "This is job B"
          - !Job
            ident  : job_c
            command: echo
            args   :
              - "This is job C"
  on_done:
    - job_that_may_pass_or_fail
  on_pass:
    - job_that_must_pass
  on_fail:
    - job_that_will_fail
```

| Field       | Required         | Description                                                                       |
|-------------|:----------------:|-----------------------------------------------------------------------------------|
| `ident`     | :material-check: | Identifier for the job array, used to navigate job hierarchy                      |
| `cwd`       |                  | Working directory, if not specified then the launch shell's `$CWD` is used        |
| `env`       |                  | Dictionary of environment variables to overlay                                    |
| `jobs`      | :material-check: | [!Job](job.md), [!JobGroup](job_group.md), or `!JobArray` to run in this tier     |
| `on_done`   |                  | List of other tasks that must complete (pass or fail) before launching this group |
| `on_pass`   |                  | List of other tasks that must succeed before launching this group                 |
| `on_fail`   |                  | List of other tasks that must fail before launching this group                    |

!!! note

    Dependencies specified in `on_done`, `on_pass`, and `on_fail` are
    ANDed together, such that all tasks listed must complete with the relevent
    pass or failure state before the dependent task is started.
