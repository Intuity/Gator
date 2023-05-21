The `!License` tag requests a particular software license to be reserved for the
execution of a particular [!Job](job.md).

It may either be specified in the compact sequence form:

```yaml
!Job
  ...
  resources:
    - !License [ToolA, 2]
```

Or in the more verbose mapping form:

```yaml
!Job
  ...
  resources:
    - !License
      name : ToolA
      count: 2
```

| Field   | Required | Description                                                   |
|---------|:--------:|---------------------------------------------------------------|
| `name`  | ✅       | Name of the license to reserve                                |
| `count` |          | Number of instances of the license to reserve (defaults to 1) |
