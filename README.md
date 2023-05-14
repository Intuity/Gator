# 🐊 Gator

Gator is a combination of a task runner and a logging system. Every job is
managed by a wrapper layer that monitors its progress, resource usage, and
captures the messages that it emits via STDOUT or STDERR. Execution is managed
in a hierarchical structure, with jobs at the leaves reporting back to layers of
parent processes.

**NOTE** This project is under development is not feature complete, nor has it
been battle tested.

## Setting Up

Gator has been developed using `poetry` for package management:

```bash
$> python3 -m pip install poetry
$> poetry install
```

## YAML Specification

Tasks to perform are specified in a custom YAML syntax, arranged into two
distinct object types:

 * `!Job` that describes a single task to perform;
 * `!JobGroup` that describes a set of tasks to perform, also supporting layers
   of nested groups;
 * `!JobArray` similar to a `!JobGroup`, but repeats the set of described tasks
   a specified number of times.

A simple specification may look like this:

```yaml
!JobGroup
  id  : top
  jobs:
  # Nested layer
  - !JobGroup
      id  : inner
      jobs:
      - !Job
          id     : say_hi
          command: echo
          args   : ["hi"]
  # Arrayed job - waits for 'say_hi' to complete
  - !JobArray
      id     : counting
      on_pass:
        - say_hi
      repeats: 4
      jobs   :
      - !Job
          id     : echo_count
          command: echo
          args   : ["$GATOR_ARRAY_INDEX"]
  # Directly attached to root - waits for 'counting' to complete
  - !Job
      id     : say_bye
      on_pass:
        - counting
      command: echo
      args   : ["bye"]
```

## Executing a Job Specification

To run a given job specification, use the Gator CLI:

```bash
$> python3 -m gator examples/job.yaml
[17:58:50] Starting Gator 🐊
           [INFO   ] Launching task: echo hey there you
           [INFO   ] Monitoring task
           [INFO   ] hey there you
           [INFO   ] Task completed with return code 0
           [INFO   ] Recorded 0 warnings and 0 errors
```

## Hub

To run the hub:

```bash
$> poe hub
```

## TODO

 * [ ] Get hub working
 * [ ] Pass artefacts between jobs and form artefact based dependencies
 * [ ] Arbitrary metrics gathering - replace warning and error counts with a generalised mechanism that supports aggregation while summarising min, max, mean, sum, and count of metrics recorded
 * [ ] Random number seeding
 * [ ] Hooks
 * [ ] Tool based log parsers
 * [ ] Custom runners - currently everything is shell, perhaps support other things?
 * [ ] Non-environment variable based parameters
