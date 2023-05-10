# Gator

Gator is a combination of a task runner and a logging system. Every job is
managed by a wrapper layer that monitors its progress, resource usage, and
captures the messages that it emits via STDOUT or STDERR. Execution is managed
in a hierarchical structure, with jobs at the leaves reporting back to layers of
parent processes.

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
   of nested groups.

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
  # Directly attached to root
  - !Job
      id     : say_bye
      command: echo
      args   : ["bye"]
  # Arrayed job
  - !JobArray
      id     : counting
      repeats: 4
      jobs   :
      - !Job
          id     : echo_count
          command: echo
          args   : ["$GATOR_ARRAY_INDEX"]
```

## Executing a Job Specification

To run a given job specification, use the Gator CLI:

```bash
$> poetry run python3 -m gator job_spec.yaml
[04/27/23 21:06:18] INFO     Layer 'top' launching sub-jobs
[04/27/23 21:06:18] INFO     Layer 'T0_inner' launching sub-jobs
                    INFO     Wrapper 'T1_say_bye' monitoring child PID 45138
                    INFO     Wrapper 'T1_say_bye' child PID 45138 finished
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
