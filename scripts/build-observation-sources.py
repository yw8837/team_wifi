"""Build the deployment allowlist exclusively from checked-in public corpus."""
import json
import os
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
os.environ.update(MODU_ENV='local',DATABASE_URL='sqlite:///:memory:',RUNTIME_DIR=str(ROOT/'.runtime/observation-source-map'))
sys.path.insert(0,str(ROOT/'backend'))
from app import knowledge
sources={chunk.source_id:chunk.revision for chunk in knowledge.corpus()}
if len(sources)>200:raise SystemExit('Public source map exceeds budget.')
(ROOT/'backend/app/observation_sources.json').write_text(json.dumps({'schema_version':1,'sources':sources},indent=2,sort_keys=True)+'\n',encoding='utf-8')
print('Built public-source allowlist:',len(sources))
