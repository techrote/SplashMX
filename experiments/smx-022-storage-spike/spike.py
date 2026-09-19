#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, math, os, platform, sqlite3, statistics, struct, subprocess, sys, tempfile, time
from pathlib import Path
from typing import Any

# Disposable SMX-022 spike harness: no production dependency.


def _head(major: int, n: int) -> bytes:
    if n < 24: return bytes([(major << 5) | n])
    if n <= 0xFF: return bytes([(major << 5) | 24, n])
    if n <= 0xFFFF: return bytes([(major << 5) | 25]) + struct.pack('>H', n)
    if n <= 0xFFFFFFFF: return bytes([(major << 5) | 26]) + struct.pack('>I', n)
    if n <= 0xFFFFFFFFFFFFFFFF: return bytes([(major << 5) | 27]) + struct.pack('>Q', n)
    raise ValueError('integer/length too large')


def cbor_encode(v: Any) -> bytes:
    if v is None: return b'\xf6'
    if v is False: return b'\xf4'
    if v is True: return b'\xf5'
    if isinstance(v, int) and not isinstance(v, bool):
        return _head(0, v) if v >= 0 else _head(1, -1-v)
    if isinstance(v, float):
        if not math.isfinite(v): raise ValueError('non-finite floats rejected')
        # Preserve -0.0 as a floating value. Use shortest IEEE form that round-trips exactly.
        for code, fmt in ((b'\xf9','>e'),(b'\xfa','>f')):
            try:
                p=struct.pack(fmt,v); r=struct.unpack(fmt,p)[0]
            except OverflowError:
                continue
            if r == v and (v != 0.0 or math.copysign(1.0,r)==math.copysign(1.0,v)):
                return code+p
        return b'\xfb'+struct.pack('>d',v)
    if isinstance(v, bytes): return _head(2,len(v))+v
    if isinstance(v, str):
        b=v.encode('utf-8'); return _head(3,len(b))+b
    if isinstance(v, list): return _head(4,len(v))+b''.join(cbor_encode(x) for x in v)
    if isinstance(v, dict):
        items=[]
        for k,val in v.items():
            if not isinstance(k,str): raise TypeError('SMX-022 profile permits string map keys only')
            kb=cbor_encode(k); items.append((kb,cbor_encode(val)))
        items.sort(key=lambda kv:kv[0])
        return _head(5,len(items))+b''.join(k+val for k,val in items)
    raise TypeError(type(v).__name__)

class CborReader:
    def __init__(self,b:bytes): self.b=b; self.i=0
    def take(self,n):
        if self.i+n>len(self.b): raise ValueError('truncated')
        x=self.b[self.i:self.i+n]; self.i+=n; return x
    def arg(self,ai):
        if ai<24:return ai
        if ai==24:return self.take(1)[0]
        if ai==25:return struct.unpack('>H',self.take(2))[0]
        if ai==26:return struct.unpack('>I',self.take(4))[0]
        if ai==27:return struct.unpack('>Q',self.take(8))[0]
        raise ValueError('indefinite/reserved additional info forbidden')
    def read(self):
        ib=self.take(1)[0]; major=ib>>5; ai=ib&31
        if major in (0,1):
            n=self.arg(ai); return n if major==0 else -1-n
        if major in (2,3):
            n=self.arg(ai); raw=self.take(n); return raw if major==2 else raw.decode('utf-8','strict')
        if major==4: return [self.read() for _ in range(self.arg(ai))]
        if major==5:
            n=self.arg(ai); d={}
            prev=None
            for _ in range(n):
                start=self.i; k=self.read(); kb=self.b[start:self.i]
                if not isinstance(k,str): raise ValueError('non-string key')
                if prev is not None and not(prev < kb): raise ValueError('duplicate or unsorted key')
                prev=kb
                if k in d: raise ValueError('duplicate key')
                d[k]=self.read()
            return d
        if major==7:
            if ai==20:return False
            if ai==21:return True
            if ai==22:return None
            if ai==25:return struct.unpack('>e',self.take(2))[0]
            if ai==26:return struct.unpack('>f',self.take(4))[0]
            if ai==27:return struct.unpack('>d',self.take(8))[0]
        raise ValueError('unsupported CBOR item')

def cbor_decode(b:bytes):
    r=CborReader(b); v=r.read()
    if r.i != len(b): raise ValueError('trailing bytes')
    return v

def json_bytes(v):
    return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')

def digest(b): return hashlib.sha256(b).hexdigest()

def protected_asset(n:int, rev:int=0):
    return {
      'asset_id':f'asset:{n:06d}',
      'revision':f'assetrev:{n:06d}:{rev}',
      'digest':hashlib.sha256(f'asset-{n}-rev-{rev}'.encode()).hexdigest(),
      'source_identity':{'kind':'imported','stable_source_id':f'source:{n:06d}'},
      'source_metadata':{'name':f'clip-{n}.wav','byte_length':4096+n,'media_type':'audio/wav'},
      'audio_or_media_semantics':{'channels':2,'sample_rate_hz':48000,'loop':False},
      'provenance':{'origin':'fixture','capture_id':f'cap:{n:06d}'},
      'licence_attribution':{'licence':'CC0-1.0','credit':'fixture'},
      'derivation_lineage':{'parents':[],'operation':'source'},
    }

def thing(n:int):
    return {
      'thing_id':f'thing:{n:08d}',
      'kind':'sprite' if n%3 else 'group',
      'name':f'Thing {n}',
      'definition_id':f'def:{n%23:04d}',
      'parent_id':None if n<2 else f'thing:{n//2:08d}',
      'state':{'x':n%401,'y':(n*17)%311,'visible':True,'label':f'obj-{n}'},
      'ports':[{'port_id':f'port:{n:08d}:in','direction':'in','type':'event'}],
    }

def connection(n:int,count:int):
    a=n%count; b=(n*37+11)%count
    return {'connection_id':f'conn:{n:08d}','from':f'thing:{a:08d}','from_port':f'port:{a:08d}:in','to':f'thing:{b:08d}','to_port':f'port:{b:08d}:in'}

def make_project(kind:str):
    if kind=='tiny': nt,nc,na=12,8,1
    elif kind=='nested': nt,nc,na=96,120,4
    elif kind=='many': nt,nc,na=1500,3000,32
    elif kind=='large': nt,nc,na=15000,30000,128
    else: raise ValueError(kind)
    records={}
    for i in range(nt): records[f'thing:{i:08d}']={'record_type':'thing','value':thing(i)}
    for i in range(nc): records[f'conn:{i:08d}']={'record_type':'connection','value':connection(i,nt)}
    for i in range(na): records[f'asset:{i:06d}']={'record_type':'asset','value':protected_asset(i)}
    records['ref:known-unloaded']={'record_type':'external_ref','value':{'target_id':'thing:known-unloaded','state':'known_unloaded','chunk_hint':'deferred'}}
    return {'schema_family':'splashmx.project','schema_version':'1.0','required_features':['thing.kernel'],'project_id':'project:smx022','project_revision_id':f'rev:{kind}:0','records':records}

def stable_bucket_pack(records:dict[str,dict], target:int):
    encoded={rid:cbor_encode({'id':rid,**rec}) for rid,rec in records.items()}
    bits=0
    def groups(bits):
        buckets={}
        for rid,b in encoded.items():
            h=int.from_bytes(hashlib.sha256(rid.encode()).digest()[:4],'big')
            key=h>>(32-bits) if bits else 0
            buckets.setdefault(key,[]).append((rid,b))
        return buckets
    while bits<20:
        buckets=groups(bits)
        # Conservative estimate includes ~70 bytes index overhead per record.
        if max(sum(len(b)+70+len(rid) for rid,b in vals) for vals in buckets.values())<=target or len(encoded)<2:
            break
        bits+=1
    chunks=[]
    for key,vals in sorted(buckets.items()):
        vals.sort(key=lambda x:x[0])
        # Deterministic local index: magic, count, then id + offset/length/digest.
        header_len=5+4+sum(2+len(rid.encode())+4+4+32 for rid,_ in vals)
        cursor=header_len
        header=bytearray(b'SMXC1')+struct.pack('>I',len(vals))
        body=bytearray()
        for rid,b in vals:
            rb=rid.encode('utf-8')
            header+=struct.pack('>H',len(rb))+rb+struct.pack('>II',cursor,len(b))+hashlib.sha256(b).digest()
            body+=b; cursor+=len(b)
        chunk=bytes(header+body)
        chunks.append({'bucket_bits':bits,'bucket':key,'bytes':chunk,'digest':digest(chunk)})
    manifest={'profile':'smx022-id-sharded-cbor/1','bucket_bits':bits,'chunks':[{'bucket':c['bucket'],'digest':c['digest'],'length':len(c['bytes'])} for c in chunks]}
    return encoded,chunks,manifest

def chunk_lookup(chunk:bytes,rid:str):
    if chunk[:5]!=b'SMXC1': raise ValueError('bad chunk magic')
    n=struct.unpack('>I',chunk[5:9])[0]; i=9
    found=None
    for _ in range(n):
        ln=struct.unpack('>H',chunk[i:i+2])[0]; i+=2
        key=chunk[i:i+ln].decode(); i+=ln
        off,length=struct.unpack('>II',chunk[i:i+8]); i+=8
        dg=chunk[i:i+32]; i+=32
        if key==rid: found=(off,length,dg)
    if not found: raise KeyError(rid)
    off,length,dg=found; b=chunk[off:off+length]
    if hashlib.sha256(b).digest()!=dg: raise ValueError('record digest mismatch')
    return b

def update_record(records,rid):
    out=dict(records); rec=json.loads(json.dumps(records[rid]))
    if rec['record_type']=='thing': rec['value']['state']['x'] += 1
    elif rec['record_type']=='asset': rec['value']=protected_asset(int(rid.split(':')[1]),1)
    out[rid]=rec; return out

def percentile(xs,p):
    xs=sorted(xs); return xs[max(0,min(len(xs)-1,round((len(xs)-1)*p)))]

def bench_encoding(kind, samples=15):
    project=make_project(kind)
    out={}
    for name,enc,dec in [('canonical_json',json_bytes,lambda b:json.loads(b)),('deterministic_cbor',cbor_encode,cbor_decode)]:
        b=enc(project); assert dec(b)==project
        # reordered maps must emit identical bytes
        reordered={k:project[k] for k in reversed(list(project.keys()))}; assert enc(reordered)==b
        et=[]; dt=[]
        for _ in range(samples):
            t=time.perf_counter_ns(); x=enc(project); et.append((time.perf_counter_ns()-t)/1e6)
            t=time.perf_counter_ns(); y=dec(x); dt.append((time.perf_counter_ns()-t)/1e6); assert y==project
        out[name]={'bytes':len(b),'encode_ms_median':statistics.median(et),'decode_ms_median':statistics.median(dt),'encode_ms_p95':percentile(et,.95),'decode_ms_p95':percentile(dt,.95)}
    return out

def bench_chunking(kind='many', samples=30):
    records=make_project(kind)['records']; rid='thing:00000100'
    out={}
    for target in (16*1024,32*1024,64*1024,256*1024):
        enc,chunks,man=stable_bucket_pack(records,target)
        new_records=update_record(records,rid); enc2,chunks2,man2=stable_bucket_pack(new_records,target)
        old={(c['bucket_bits'],c['bucket']):c for c in chunks}; new={(c['bucket_bits'],c['bucket']):c for c in chunks2}
        changed=set(old)^set(new)
        changed |= {k for k in set(old)&set(new) if old[k]['digest']!=new[k]['digest']}
        changed_bytes=sum(len(new[k]['bytes']) for k in changed if k in new)
        manifest_bytes=len(cbor_encode(man)); manifest2_bytes=len(cbor_encode(man2))
        bits=man['bucket_bits']; h=int.from_bytes(hashlib.sha256(rid.encode()).digest()[:4],'big'); bucket=h>>(32-bits) if bits else 0
        c=next(x for x in chunks if x['bucket']==bucket); sl=chunk_lookup(c['bytes'],rid)
        assert cbor_decode(sl)['id']==rid
        partial=[]; mono=[]; monob=cbor_encode(make_project(kind))
        for _ in range(samples):
            t=time.perf_counter_ns(); cbor_decode(chunk_lookup(c['bytes'],rid)); partial.append((time.perf_counter_ns()-t)/1e6)
            t=time.perf_counter_ns(); cbor_decode(monob)['records'][rid]; mono.append((time.perf_counter_ns()-t)/1e6)
        out[str(target)]={'bucket_bits':bits,'chunk_count':len(chunks),'root_manifest_bytes':manifest_bytes,'changed_chunk_count':len(changed),'changed_chunk_bytes':changed_bytes,'new_root_manifest_bytes':manifest2_bytes,'changed_record_bytes':len(enc2[rid]),'write_amplification_vs_record':(changed_bytes+manifest2_bytes)/max(1,len(enc2[rid])),'partial_read_ms_median':statistics.median(partial),'monolithic_read_ms_median':statistics.median(mono)}
    return out

def sqlite_init(path:Path, journal:str):
    con=sqlite3.connect(path)
    con.execute(f'PRAGMA journal_mode={journal}')
    con.execute('PRAGMA synchronous=FULL')
    con.executescript('''
      CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT NOT NULL);
      CREATE TABLE records(semantic_id TEXT PRIMARY KEY, record_type TEXT NOT NULL, canonical BLOB NOT NULL, digest TEXT NOT NULL, revision TEXT NOT NULL);
      CREATE TABLE revisions(revision TEXT PRIMARY KEY, parent TEXT, committed_at INTEGER NOT NULL);
    ''')
    records=make_project('nested')['records']
    con.execute('BEGIN IMMEDIATE')
    for rid,rec in records.items():
        b=cbor_encode({'id':rid,**rec}); con.execute('INSERT INTO records VALUES(?,?,?,?,?)',(rid,rec['record_type'],b,digest(b),'r0'))
    con.execute('INSERT INTO revisions VALUES(?,?,?)',('r0',None,0)); con.execute('INSERT INTO meta VALUES(?,?)',('head','r0'))
    con.commit(); con.close()

def sqlite_child(db:str,journal:str,mode:str):
    con=sqlite3.connect(db); con.execute(f'PRAGMA journal_mode={journal}'); con.execute('PRAGMA synchronous=FULL'); con.execute('BEGIN IMMEDIATE')
    rid='asset:000000'; b=cbor_encode({'id':rid,'record_type':'asset','value':protected_asset(0,1)})
    con.execute('UPDATE records SET canonical=?, digest=?, revision=? WHERE semantic_id=?',(b,digest(b),'r1',rid))
    con.execute('INSERT OR REPLACE INTO revisions VALUES(?,?,?)',('r1','r0',1)); con.execute("UPDATE meta SET v='r1' WHERE k='head'")
    if mode=='crash': os._exit(23)
    con.commit(); os._exit(0)

def validate_sqlite(path:Path):
    con=sqlite3.connect(path); head=con.execute("SELECT v FROM meta WHERE k='head'").fetchone()[0]
    row=con.execute("SELECT canonical,revision FROM records WHERE semantic_id='asset:000000'").fetchone(); obj=cbor_decode(row[0]); con.close()
    rev=obj['value']['revision']
    if head=='r0': assert row[1]=='r0' and rev.endswith(':0')
    elif head=='r1': assert row[1]=='r1' and rev.endswith(':1')
    else: raise AssertionError(head)
    return head

def bench_sqlite(journal='WAL',samples=12):
    lats=[]
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/'p.db'; sqlite_init(p,journal)
        initial=p.stat().st_size
        # Abrupt pre-commit and post-commit process exits validate recovery semantics.
        cp=subprocess.run([sys.executable,__file__,'sqlite-child',str(p),journal,'crash']); assert cp.returncode==23; assert validate_sqlite(p)=='r0'
        cp=subprocess.run([sys.executable,__file__,'sqlite-child',str(p),journal,'commit']); assert cp.returncode==0; assert validate_sqlite(p)=='r1'
        # Measure actual transaction time in-process; do not count interpreter startup.
        q=Path(td)/'perf.db'; sqlite_init(q,journal)
        con=sqlite3.connect(q); con.execute(f'PRAGMA journal_mode={journal}'); con.execute('PRAGMA synchronous=FULL')
        if journal.upper()=='WAL': con.execute('PRAGMA wal_autocheckpoint=0')
        for i in range(samples):
            rev=f'p{i+2}'; rid='asset:000000'; b=cbor_encode({'id':rid,'record_type':'asset','value':protected_asset(0,(i+2)%2)})
            t=time.perf_counter_ns(); con.execute('BEGIN IMMEDIATE'); con.execute('UPDATE records SET canonical=?, digest=?, revision=? WHERE semantic_id=?',(b,digest(b),rev,rid)); con.execute('INSERT OR REPLACE INTO revisions VALUES(?,?,?)',(rev,'r1',i+2)); con.execute("UPDATE meta SET v=? WHERE k='head'",(rev,)); con.commit(); lats.append((time.perf_counter_ns()-t)/1e6)
        wal_bytes=(Path(str(q)+'-wal').stat().st_size if Path(str(q)+'-wal').exists() else 0)
        con.close(); final=p.stat().st_size
    return {'journal_mode':journal,'synchronous':'FULL','crash_before_commit_head':'r0','abrupt_after_commit_head':'r1','commit_ms_median':statistics.median(lats),'commit_ms_p95':percentile(lats,.95),'db_bytes_initial':initial,'db_bytes_final':final,'wal_bytes_after_samples_before_close':wal_bytes}

def fsync_dir(path:Path):
    fd=os.open(path,os.O_DIRECTORY); os.fsync(fd); os.close(fd)

def atomic_file_init(root:Path):
    root.mkdir(); rec=cbor_encode(make_project('nested')); (root/'r0.cbor').write_bytes(rec)
    with open(root/'r0.cbor','rb') as f: os.fsync(f.fileno())
    (root/'HEAD').write_text('r0',encoding='ascii');
    with open(root/'HEAD','rb') as f: os.fsync(f.fileno())
    fsync_dir(root)

def atomic_file_child(root_s:str,stage:str):
    root=Path(root_s); b=cbor_encode({**make_project('nested'),'project_revision_id':'rev:nested:1'})
    tmp=root/'r1.tmp'
    with open(tmp,'wb') as f: f.write(b); f.flush(); os.fsync(f.fileno())
    os.replace(tmp,root/'r1.cbor'); fsync_dir(root)
    if stage=='before-head': os._exit(24)
    htmp=root/'HEAD.tmp'
    with open(htmp,'w',encoding='ascii') as f: f.write('r1'); f.flush(); os.fsync(f.fileno())
    os.replace(htmp,root/'HEAD'); fsync_dir(root); os._exit(0)

def validate_atomic(root:Path):
    h=(root/'HEAD').read_text().strip(); b=(root/f'{h}.cbor').read_bytes(); obj=cbor_decode(b); assert obj['project_revision_id'].endswith(':0') if h=='r0' else obj['project_revision_id'].endswith(':1'); return h

def atomic_file_commit(root:Path, revision:str, project:dict):
    b=cbor_encode(project); rev_path=root/f'{revision}.cbor'; tmp=root/f'{revision}.tmp'
    with open(tmp,'wb') as f: f.write(b); f.flush(); os.fsync(f.fileno())
    os.replace(tmp,rev_path); fsync_dir(root)
    htmp=root/'HEAD.tmp'
    with open(htmp,'w',encoding='ascii') as f: f.write(revision); f.flush(); os.fsync(f.fileno())
    os.replace(htmp,root/'HEAD'); fsync_dir(root)
    return len(b)+len(revision)

def bench_atomic_file(samples=8):
    lats=[]; written=[]
    with tempfile.TemporaryDirectory() as td:
        r=Path(td)/'s'; atomic_file_init(r); initial=sum(p.stat().st_size for p in r.iterdir())
        cp=subprocess.run([sys.executable,__file__,'file-child',str(r),'before-head']); assert cp.returncode==24; assert validate_atomic(r)=='r0'
        for p in r.iterdir():
            if p.name not in ('r0.cbor','HEAD'): p.unlink()
        cp=subprocess.run([sys.executable,__file__,'file-child',str(r),'commit']); assert cp.returncode==0; assert validate_atomic(r)=='r1'
        final=sum(p.stat().st_size for p in r.iterdir())
        perf=Path(td)/'perf'; atomic_file_init(perf)
        for i in range(samples):
            pr={**make_project('nested'),'project_revision_id':f'rev:nested:{i+2}'}
            t=time.perf_counter_ns(); written.append(atomic_file_commit(perf,f'r{i+2}',pr)); lats.append((time.perf_counter_ns()-t)/1e6)
    return {'crash_before_head':'r0','abrupt_after_head':'r1','commit_ms_median':statistics.median(lats),'commit_ms_p95':percentile(lats,.95),'bytes_written_per_commit_median':statistics.median(written),'bytes_initial':initial,'bytes_after_two_revisions':final}

def hardware_info():
    cpu='unknown'
    try:
        for line in Path('/proc/cpuinfo').read_text().splitlines():
            if line.lower().startswith('model name'):
                cpu=line.split(':',1)[1].strip(); break
    except OSError: cpu=platform.processor() or 'unknown'
    try:
        memory_bytes=int(os.sysconf('SC_PAGE_SIZE')*os.sysconf('SC_PHYS_PAGES'))
    except (ValueError,OSError,AttributeError): memory_bytes=0
    return {'cpu':cpu,'gpu':'none','memory_bytes':memory_bytes}

def main():
    if len(sys.argv)>1 and sys.argv[1]=='sqlite-child': sqlite_child(sys.argv[2],sys.argv[3],sys.argv[4])
    if len(sys.argv)>1 and sys.argv[1]=='file-child': atomic_file_child(sys.argv[2],sys.argv[3])
    parser=argparse.ArgumentParser(); parser.add_argument('--output'); args=parser.parse_args()
    result={'contract':'splashmx.smx022-spike-results/1','captured_at_utc':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'runtime':{'name':'CPython','version':platform.python_version(),'build_id':platform.python_build()[0]},'environment':{'os':f'{platform.system()} {platform.release()}','arch':platform.machine(),'hardware':hardware_info()},'encoding':{},'chunking':{},'native_persistence':{}}
    for kind in ('tiny','nested','many'):
        result['encoding'][kind]=bench_encoding(kind)
    result['chunking']=bench_chunking('many')
    result['native_persistence']['sqlite_wal_full']=bench_sqlite('WAL')
    result['native_persistence']['sqlite_delete_full']=bench_sqlite('DELETE')
    result['native_persistence']['atomic_revision_files']=bench_atomic_file()
    text=json.dumps(result,indent=2,sort_keys=True)+'\n'
    if args.output: Path(args.output).write_text(text,encoding='utf-8')
    else: print(text,end='')

if __name__=='__main__': main()
