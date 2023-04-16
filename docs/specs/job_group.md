A `!JobGroup` can specify a collection of jobs to be executed by Gator, each
grouping can contain instances of [!Job](job.md) or nested `JobGroup` layers:

```yaml
!JobGroup:
  id  : top
  jobs:
    - !Job
      id     : job_a
      command: echo
      args   :
       - "This is job A"
    - !JobGroup
        id  : inner
        jobs:
          - !Job
            id     : job_b
            command: echo
            args   :
              - "This is job B"
          - !Job
            id     : job_c
            command: echo
            args   :
              - "This is job C"
```
