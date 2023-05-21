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

```yaml
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
