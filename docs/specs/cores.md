The `!Cores` tag specifies the maximum number of CPU cores expected for a
[!Job](job.md) and will be used by the scheduler to reserve a suitably sliced
slot on the compute infrastructure.

It may either be specified in the compact sequence form or verbose mapping form:

=== "Sequence Form"

    ```yaml linenums="1"
    !Job
      ...
      resources:
        - !Cores [3]
    ```

=== "Mapping Form"

    ```yaml linenums="1"
    !Job
      ...
      resources:
        - !Cores
          count: 3
    ```

| Field   | Required         | Description                |
|---------|:----------------:|----------------------------|
| `cores` | :material-check: | Number of cores to reserve |
