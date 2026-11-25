"""RSS watchdog for this Opik supervisor tree only; never signals existing services."""
import json
from pathlib import Path
import subprocess
import sys
import time
import os

runtime=Path(sys.argv[1]);root=runtime.parents[1]
limit=8*1024**3
names=['mysql','redis','zookeeper','clickhouse','minio','backend','frontend']
while True:
    try:
        pending=[int((runtime/'run/supervisord.pid').read_text())];seen=set();rss=0
        while pending:
            pid=pending.pop()
            if pid in seen:continue
            seen.add(pid)
            process=Path('/proc')/str(pid)
            try:
                rss+=int((process/'statm').read_text().split()[1])*os.sysconf('SC_PAGE_SIZE')
                pending.extend(map(int,(process/'task'/str(pid)/'children').read_text().split()))
            except (FileNotFoundError,ProcessLookupError):pass
        if rss>limit:
            print(json.dumps({'event':'opik_rss_budget_exceeded','rss_bytes':rss,'budget_bytes':limit,'action':'stop_only_opik_components'}),flush=True)
            subprocess.run([str(root/'.venv/bin/supervisorctl'),'-c',str(runtime/'conf/supervisord.conf'),'stop',*['opik-'+name for name in names]],capture_output=True,timeout=90)
    except (OSError,ValueError,subprocess.TimeoutExpired):
        print('Opik RSS watchdog could not sample its private process tree',flush=True)
    time.sleep(3)
