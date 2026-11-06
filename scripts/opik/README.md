# Native Opik sandbox

This installs the pinned official Opik 2.2.142 artifacts without Docker, mounts,
chroot, or user namespaces. It is isolated in `/home/elicer/Team_Wifi/.runtime/opik`.
It does not control the existing API, model, 8080 process, or existing supervisor.

Run only from `/home/elicer/Team_Wifi`, using the authorized SSH connection:

```sh
python3 scripts/setup-native-opik.py inventory
python3 scripts/setup-native-opik.py prepare
python3 scripts/setup-native-opik.py configure
python3 scripts/setup-native-opik.py infra
python3 scripts/setup-native-opik.py migrate
python3 scripts/setup-native-opik.py application
.runtime/opik/venv/bin/python scripts/setup-native-opik.py verify
python3 scripts/setup-native-opik.py status
```

The separate SDK environment is created with all temporary/cache files in the runtime:

```sh
export HOME=/home/elicer/Team_Wifi/.runtime/opik/home
export TMPDIR=/home/elicer/Team_Wifi/.runtime/opik/tmp
export PIP_CACHE_DIR=/home/elicer/Team_Wifi/.runtime/opik/pip-cache
python3 -m venv .runtime/opik/venv
.runtime/opik/venv/bin/python -m pip install --cache-dir .runtime/opik/pip-cache -r backend/requirements-opik.txt
```

Public OCI manifests and every downloaded layer are verified against SHA256.
Resolved platform manifest digests are recorded in `.runtime/opik/provenance.json`.
No system packages are installed. Linux ELF dependencies are reused from the
matching image prefix; Redis uses its extracted musl loader explicitly.

All listeners bind to 127.0.0.1:

| Component | Port |
|---|---:|
| Frontend static files and `/api` proxy | 15173 |
| Java API | 18080 |
| Java admin | 18081 |
| MySQL | 13306 |
| Redis | 16379 |
| ZooKeeper | 12181 |
| ClickHouse HTTP / native / replication HTTP | 18123 / 19090 / 19091 |
| MinIO / optional console | 19000 / 19001 |

The frontend serves the extracted official dist with a bounded, loopback-only
Python proxy. SDK host is `http://127.0.0.1:15173/api`; workspace is `default`.
OSS authentication is disabled. Do not expose these ports publicly. Use an
operator SSH tunnel when accessing the UI from another machine.

Credentials and launch configuration are generated with mode 0600 under the
mode-0700 runtime directory. MySQL root is also password protected after bootstrap.
Never copy those files, logs, caches or database files into Git.

Java has a 1536MiB heap and 256MiB direct-memory cap. ClickHouse is capped at 2GiB,
MySQL's buffer pool at 512MiB, Redis at 128MiB, ZooKeeper heap at 384MiB, MinIO's
Go memory target at 256MiB, and the frontend address space at 512MiB. A separate
watchdog samples only this supervisor's process tree every three seconds; above
8GiB RSS it stops only these Opik components. These are sandbox bounds, not a
throughput or production capacity claim.

On the shared Elice cgroup, ClickHouse must use
`memory_worker_use_cgroup=0`; otherwise the memory of the existing API/model is
miscounted as ClickHouse's own memory. Its 2GiB limit remains enabled. Historical migration 000017 requires Liquibase journals in the ClickHouse
`default` database, so the migration JDBC URL has no `/opik` suffix. Actual
analytics tables remain in `opik`. Query
parallelism is two; IO thread pool 16; global pool 256 so permanent background
workers do not exhaust admission.

Only this supervisor is controlled by:

```sh
.venv/bin/supervisorctl -c .runtime/opik/conf/supervisord.conf status
```

Its private socket and PID live in `.runtime/opik/run/`. Existing
`.runtime/supervisord.conf` is not modified. No boot service or scheduled startup
is installed. After a machine/container restart, start the recorded phases again.
Do not rerun MySQL initialization against a populated datadir.

Usage reporting, product analytics, automatic external evaluators and OTEL
instrumentation are disabled. Validation uses only randomly generated trace IDs
and empty input/output plus allowlisted metadata. `verification.json` records an
actual SDK flush, HTTP fetch through `/api`, fetch after restarting only the Opik
backend, loopback bindings, and service RSS. It is not evidence of model
inference; the assistant's separate frozen evaluation supplies that evidence.

The assistant uses `local_extractive` for successful real local-model inference:
the model selects at most two approved public source IDs and zero-based
sentence indices. The server looks up those exact complete source sentences/lines
from the context that was supplied. It does not freely
paraphrase them. `retrieval_only` is the non-model source-excerpt fallback, and
`abstained` covers unsupported requests. Prompt version is
`extractive-index-v3`. Neither source selection nor a valid citation alone
is a human relevance/groundedness score.

To verify the actual forty-case synthetic evaluation in Opik, after the root
evaluation process has finished and drained its SDK queue:

```sh
.runtime/opik/venv/bin/python scripts/opik/query_evaluation_traces.py \
  --evaluation-report .runtime/assistant-evaluation/ACTUAL_REPORT.json \
  --project moduyuga-public-assistant --expected-count 40
```

This read-only SDK verifier matches all expected random request IDs, fetches full
untruncated traces again, requires null input/output and validates metadata
against the public corpus versions in the synthetic evaluation report. It never
copies or prints captured contents. Output is private
`.runtime/opik/evaluation-traces-verification.json`. The bundled fixture hash is
checked before querying; an unrelated member conversation export is rejected.
