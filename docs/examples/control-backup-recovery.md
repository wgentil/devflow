# Retry an interrupted control backup

Optional developer example. Plugin users ask the harness to back up control
storage; they need no shell setup or command names. Maintainers using `df` follow
its optional [developer setup](../developer-cli.md). Replace the example absolute
paths with an owned control root and a new backup destination.

```sh
df state backup --root /path/project/.devflow/control --output /path/owned-backup --operation-id backup-2026 --actor-id maintainer
```

If copying is interrupted, run the **identical command**. Its operation, actor and
output identity authorize resuming only its own incomplete output:

```sh
df state backup --root /path/project/.devflow/control --output /path/owned-backup --operation-id backup-2026 --actor-id maintainer
```

A completed exact retry returns the original receipt and snapshot. To capture
later work, use a new operation ID **and** a new output directory. An unrelated
completed/incomplete output is refused without modification. Do not delete its
ownership marker or substitute another root's backup. See the
[maintenance reference](../reference/control-maintenance.md) for verification,
backup limits and recovery.
