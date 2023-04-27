A `!Job` specifies a single action to perform along with the environment that it
should be executed within:

```yaml
!Job
  id     : test_job
  cwd    : /path/to/working/directory
  command: echo
  args   :
    - "This is key A: $ENV_KEY_A and B: $ENV_KEY_B"
  env    :
    ENV_KEY_A: abcde
    ENV_KEY_B: 12345
```
