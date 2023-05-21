<table style="border:none;">
    <tbody>
        <tr style="border:none;">
            <td style="border:none;width:25%;">
                <img src="assets/mascot_white.png" width="100%" />
            </td>
            <td style="border:none;font-size:16px;vertical-align:middle;">
                Gator is a framework for running a hierarchy of jobs and
                aggregating logs, metrics, resource utilisation, and artefacts.
            </td>
        </tr>
    </tbody>
</table>

## Getting Started

Gator is compatible with Python version 3.8 through 3.11 and is developed using
[the Poetry packaging tool](https://python-poetry.org). To install Gator, check
out the repository from GitHub and install it with Poetry:

```bash
$> git clone git@github.com:/Intuity/Gator.git
$> cd Gator
$> poetry install
```

## Running Jobs

Before running Gator, you will need to create a [job specification](#job-specifications)
as described below. Then invoke the tool as follows:

```bash
$> gator my_job_spec.yaml --progress
[17:34:49] [INFO   ] Launching task: echo hello
           [INFO   ] Monitoring task
           [INFO   ] hello
           [INFO   ] Task completed with return code 0
           [INFO   ] Recorded 0 critical, 0 error, 0 warning, 4 info and 2 debug messages
```

!!! note

    The `--progress` switch enables a progress bar which tracks jobs as they
    running and the number of passes and failures.

## Job Specifications

The complete set of tasks to run are specified with three objects:

 * [!Job](specs/job.md) - specifies a single task to run along with the working
   directory, environment variables, and required resources;
 * [!JobGroup](specs/job_group.md) - groups a collection of different jobs
   together into a named tier;
 * [!JobArray](specs/job_array.md) - similar to a [!JobGroup](specs/job_group.md)
   but it repeats the group of jobs multiple times.

Jobs, groups, and arrays can form dependencies on one another, allowing jobs to
be sequenced and only start when a previous job completes (either with success
or failure).

A simple example of the syntax can be seen below:

```yaml title="regression.yaml" linenums="1"
!JobGroup
  id  : regression
  jobs:
  # Run the build first
  - !Job
    id     : build
    command: make
    args   :
      - build
  # Launch a series of simulations once the build completes
  - !JobArray
    id     : simulations
    on_pass: [build]
    repeats: 20
    jobs   :
    - !Job
      id     : simulate
      command: make
      args   :
        - run
        - SEED=${GATOR_ARRAY_INDEX}
  # Generate reports after all simulations complete
  - !JobGroup
    id     : reports
    on_pass: [simulations]
    jobs   :
    # Merge test coverage
    - !Job
      id     : coverage
      command: make
      args   :
        - merge_coverage
```

## Acknowledgements

Project mascot: Alligator by TRAVIS BIRD from the Noun Project

A lot of the ideas in this project have been taken from the experiments detailed
on [Rich Porter's blog](http://dungspreader.blogspot.com) from 2013 and 2014.
