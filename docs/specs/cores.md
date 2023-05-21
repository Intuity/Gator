The `!Cores` tag specifies the maximum number of CPU cores expected for a
[!Job](job.md) and will be used by the scheduler to reserve a suitably sliced
slot on the compute infrastructure.

It may either be specified in the compact sequence form:

```yaml
!Job
  ...
  resources:
    - !Cores [3]
```

Or in the more verbose mapping form:

```yaml
!Job
  ...
  resources:
    - !Cores
      count: 3
```

| Field   | Required | Description                |
|---------|:--------:|----------------------------|
| `cores` | ✅       | Number of cores to reserve |
