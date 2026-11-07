#!/usr/bin/env python3
"""Install pinned native Opik in its isolated runtime. Never changes existing services."""
import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parent/'opik'))
from oci import OCI,file_hash

ROOT=Path(__file__).resolve().parents[1]
RUNTIME=ROOT/'.runtime/opik'
IMAGES={
 'backend':'ghcr.io/comet-ml/opik/opik-backend:2.2.142',
 'frontend':'ghcr.io/comet-ml/opik/opik-frontend:2.2.142',
 'mysql':'docker.io/library/mysql:8.4.2',
 'redis':'docker.io/library/redis:7.2.4-alpine3.19',
 'clickhouse':'docker.io/clickhouse/clickhouse-server:26.3.62.3-alpine',
 'zookeeper':'docker.io/library/zookeeper:3.9.4',
 'minio':'docker.io/cloudpirates/image-minio:RELEASE.2025-10-15T17-29-55Z-hardened',
}
PORTS={'backend':18080,'backend_admin':18081,'frontend':15173,'mysql':13306,'redis':16379,
       'zookeeper':12181,'clickhouse_http':18123,'clickhouse_native':19090,'clickhouse_replication':19091,'minio':19000,'minio_console':19001}


def initialize():
    if ROOT.as_posix()!='/home/elicer/Team_Wifi':raise RuntimeError('Run only in the authorized remote root')
    os.umask(0o077)
    for name in ['cache','images','conf','data','logs','run','tmp','home','pip-cache']:(RUNTIME/name).mkdir(parents=True,exist_ok=True)
    RUNTIME.chmod(0o700)


def available_ports():
    for name,port in PORTS.items():
        with socket.socket() as sock:
            try:sock.bind(('127.0.0.1',port))
            except OSError:raise RuntimeError('Reserved Opik port occupied: '+name+' '+str(port)) from None
    print('All reserved native Opik loopback ports are available',flush=True)


def prepare(components):
    provenance={}
    for name in components:
        provenance[name]=OCI(IMAGES[name],RUNTIME/'cache').extract(RUNTIME/'images'/name)
    path=RUNTIME/'provenance.json'
    old=json.loads(path.read_text()) if path.exists() else {}
    path.write_text(json.dumps({**old,**provenance},indent=2)+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['inventory','prepare','configure','infra','migrate','application','verify','status'])
    parser.add_argument('--components',nargs='+',choices=list(IMAGES),default=list(IMAGES))
    args=parser.parse_args();initialize()
    if args.phase=='inventory':available_ports();print(json.dumps({'root':str(ROOT),'ports':PORTS,'images':IMAGES},indent=2))
    elif args.phase=='prepare':prepare(args.components)
    else:
        from manage import configure,start_infrastructure,migrate,start_application,ctl
        if args.phase=='configure':configure(ROOT)
        elif args.phase=='infra':start_infrastructure()
        elif args.phase=='migrate':migrate()
        elif args.phase=='application':start_application()
        elif args.phase=='status':print(ctl('status'))
        elif args.phase=='verify':
            from verify import verify
            verify()


if __name__=='__main__':main()
