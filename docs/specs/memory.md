The `!Memory` tag specifies the maximum memory usage expected for a [!Job](job.md)
and will be used by the scheduler to reserve a suitably sliced slot on the compute
infrastructure.

It may either be specified in the compact sequence form or verbose mapping form:

=== "Sequence Form"

    ```yaml linenums="1"
    !Job
      ...
      resources:
        - !Memory [1.5, GB]
    ```

=== "Mapping Form"

    ```yaml linenums="1"
    !Job
      ...
      resources:
        - !Memory
          size: 1.5
          unit: GB
    ```

| Field  | Required         | Description                                                     |
|--------|:----------------:|-----------------------------------------------------------------|
| `size` | :material-check: | Amount of memory to reserve                                     |
| `unit` |                  | Units of the request (either KB, MB, GB, or TB, defaults to MB) |
