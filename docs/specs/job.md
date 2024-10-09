A `!Job` specifies a single action to perform along with the environment that it
should be executed within:

```yaml linenums="1"
!Job
  ident: test_job
  cwd      : /path/to/working/directory
  command  : echo
  args     :
    - "This is key A: $ENV_KEY_A and B: $ENV_KEY_B"
  env      :
    ENV_KEY_A: abcde
    ENV_KEY_B: 12345
  resources:
    - !Cores [2]
    - !Memory [1.5, GB]
    - !License [ToolA, 1]
    - !License [ToolB, 2]
  on_done  :
    - job_that_may_pass_or_fail
  on_pass  :
    - job_that_must_pass
  on_fail  :
    - job_that_will_fail
```

| Field       | Required         | Description                                                                           |
|-------------|:----------------:|---------------------------------------------------------------------------------------|
| `ident`     | :material-check: | Identifier for the job, used to navigate job hierarchy                                |
| `cwd`       |                  | Working directory, if not specified then the launch shell's `$CWD` is used            |
| `command`   | :material-check: | Command to execute                                                                    |
| `args`      |                  | List of arguments to provide to the command                                           |
| `env`       |                  | Dictionary of environment variables to overlay                                        |
| `resources` |                  | List of [!Cores](cores.md), [!Memory](memory.md), and [!License](license.md) requests |
| `on_done`   |                  | List of jobs that must complete (pass or fail) before launching this job              |
| `on_pass`   |                  | List of jobs that must succeed before launching this job                              |
| `on_fail`   |                  | List of jobs that must fail before launching this job                                 |

!!! note

    Dependencies specified in `on_done`, `on_pass`, and `on_fail` are
    ANDed together, such that all tasks listed must complete with the relevent
    pass or failure state before the dependent task is started.
