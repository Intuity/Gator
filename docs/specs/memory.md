The `!Memory` tag specifies the maximum memory usage expected for a [!Job](job.md)
and will be used by the scheduler to reserve a suitably sliced slot on the compute
infrastructure.

It may either be specified in the compact sequence form:

```yaml
!Job
  ...
  resources:
    - !Memory [1.5, GB]
```

Or in the more verbose mapping form:

```yaml
!Job
  ...
  resources:
    - !Memory
      size: 1.5
      unit: GB
```

| Field  | Required | Description                                                     |
|--------|:--------:|-----------------------------------------------------------------|
| `size` | ✅       | Amount of memory to reserve                                     |
| `unit` |          | Units of the request (either KB, MB, GB, or TB, defaults to MB) |
