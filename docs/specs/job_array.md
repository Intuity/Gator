A `!JobArray` is similar to a [!JobGroup](job_group.md) in that it may contain
multiple [!Job](job.md) and [!JobGroup](job_group.md) instances, but unlike a
[!JobGroup](job_group.md) the child jobs are repeated a specified number of
times.

```yaml
!JobArray
  id     : top
  repeats: 4
  jobs   :
    - !Job
        id     : echo_count
        command: echo
        args   :
          - "${GATOR_ARRAY_INDEX}"
```
