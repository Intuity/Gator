The `!License` tag requests a particular software license to be reserved for the
execution of a particular [!Job](job.md).

It may either be specified in the compact sequence form or verbose mapping form:

=== "Sequence Form"

    ```yaml linenums="1"
    !Job
      ...
      resources:
        - !License [ToolA, 2]
    ```

=== "Mapping Form"

    ```yaml linenums="1"
    !Job
      ...
      resources:
        - !License
          name : ToolA
          count: 2
    ```

| Field   | Required         | Description                                                   |
|---------|:----------------:|---------------------------------------------------------------|
| `name`  | :material-check: | Name of the license to reserve                                |
| `count` |                  | Number of instances of the license to reserve (defaults to 1) |
