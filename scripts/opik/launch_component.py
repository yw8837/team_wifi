"""Launch only one named native Opik component with private environment and resource knobs."""
import json
import os
from pathlib import Path
import resource
import sys

runtime=Path(sys.argv[1]);component=sys.argv[2]
configuration=json.loads((runtime/'conf/launch.json').read_text())
entry=configuration[component]
os.umask(0o077)
os.environ.update(entry.get('env',{}))
os.environ.update({'HOME':str(runtime/'home'),'TMPDIR':str(runtime/'tmp')})
soft,hard=resource.getrlimit(resource.RLIMIT_NOFILE)
resource.setrlimit(resource.RLIMIT_NOFILE,(min(65536,hard),hard))
resource.setrlimit(resource.RLIMIT_CORE,(0,0))
if component in ('frontend','guard'):
    bound=(512 if component=='frontend' else 128)*1024**2
    resource.setrlimit(resource.RLIMIT_AS,(bound,bound))
os.chdir(entry.get('cwd',str(runtime)))
os.execvpe(entry['command'][0],entry['command'],os.environ)
