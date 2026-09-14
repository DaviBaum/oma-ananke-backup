"""Match bundled DLL hashes to conda build records and preserve source recipes/notices."""
from native_probe import OUT, SITES, fetch
from pathlib import Path
import concurrent.futures, ctypes, hashlib, io, json, struct, tarfile, zipfile

def section_hashes(raw):
    pe=struct.unpack_from('<I',raw,60)[0]
    assert raw[pe:pe+4]==b'PE\0\0'
    count=struct.unpack_from('<H',raw,pe+6)[0];optional_size=struct.unpack_from('<H',raw,pe+20)[0]
    output={}
    for i in range(count):
        at=pe+24+optional_size+40*i
        name=raw[at:at+8].rstrip(b'\0').decode();length,offset=struct.unpack_from('<II',raw,at+16)
        output[name]={'sha256':hashlib.sha256(raw[offset:offset+length]).hexdigest(),'bytes':length}
    return output

def unpack(raw):
    import OCP
    mod=ctypes.CDLL(str(next((SITES/'cadquery_ocp.libs').glob('zstd-*.dll'))))
    size=mod.ZSTD_getFrameContentSize;size.argtypes=[ctypes.c_void_p,ctypes.c_size_t];size.restype=ctypes.c_ulonglong
    decompress=mod.ZSTD_decompress;decompress.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p,ctypes.c_size_t];decompress.restype=ctypes.c_size_t
    error=mod.ZSTD_isError;error.argtypes=[ctypes.c_size_t];error.restype=ctypes.c_uint
    n=size(raw,len(raw));n=128*1024**2 if n>=2**64-2 else n
    if n>256*1024**2: raise ValueError('frame too large')
    buf=ctypes.create_string_buffer(n);result=decompress(buf,n,raw,len(raw))
    if error(result): raise ValueError('ZSTD decompression failed')
    return buf.raw[:result]

def inspect(item):
    row, artifact=item
    if 'error' in artifact: return artifact
    filename=artifact['file'];target=OUT/'conda-records'/Path(filename).stem;target.mkdir(parents=True,exist_ok=True)
    package=OUT/filename
    if package.suffix=='.conda':
        with zipfile.ZipFile(package) as z:
            data=unpack(z.read(next(n for n in z.namelist() if n.startswith('info-'))))
        archive=tarfile.open(fileobj=io.BytesIO(data))
    else: archive=tarfile.open(package)
    retained=[];dlls=[]
    for member in archive:
        if not member.isfile() or not member.name.startswith('info/'): continue
        name=Path(member.name)
        if member.name=='info/paths.json':
            paths=json.load(archive.extractfile(member))
            dlls=[p for p in paths['paths'] if p['_path'].lower().endswith('.dll')]
        if member.name.startswith(('info/licenses/','info/recipe/')) or member.name in ['info/about.json','info/index.json','info/paths.json','info/hash_input.json','info/git']:
            if '..' in name.parts: raise ValueError('invalid archive path')
            dest=target/name;dest.parent.mkdir(parents=True,exist_ok=True);raw=archive.extractfile(member).read();dest.write_bytes(raw)
            retained.append({'path':str(dest.relative_to(OUT)), 'sha256':hashlib.sha256(raw).hexdigest()})
    if package.suffix=='.conda':
        with zipfile.ZipFile(package) as z:
            data=unpack(z.read(next(n for n in z.namelist() if n.startswith('pkg-'))))
        payload=tarfile.open(fileobj=io.BytesIO(data))
    else: payload=tarfile.open(package)
    for d in dlls:
        raw=payload.extractfile(d['_path']).read()
        if hashlib.sha256(raw).hexdigest()!=d['sha256']: raise ValueError('Conda DLL digest mismatch')
        d['pe_sections']=section_hashes(raw)
    if artifact['sha256']!=row['sha256']: raise ValueError('Conda download digest mismatch')
    return {'package':row['basename'],'version':row['version'],'artifact':artifact,'package_metadata':row,'dlls':dlls,'retained':retained}

if __name__=='__main__':
    packages=['libdeflate','freeimage','freetype','libpng','libwebp-base','openjpeg','libraw','openjph','openexr','imath','lerc','libjpeg-turbo','lcms2','libtiff','zlib','zstd','vc14_runtime']
    chosen=[]
    for name in packages:
        meta=json.loads((OUT/(name+'-conda.json')).read_text())
        options=[r for r in meta['files'] if r.get('attrs',{}).get('subdir')=='win-64' and r['upload_time']<'2026-09-06' and (name!='freetype' or r['version'].startswith('2.12.'))]
        options.sort(key=lambda r:r['upload_time'],reverse=True);chosen.append(options[0])
    downloads=list(concurrent.futures.ThreadPoolExecutor(8).map(fetch,[(r['basename'].split('/')[-1],'https:'+r['download_url']) for r in chosen]))
    results=[]
    for item in zip(chosen,downloads):
        r=inspect(item);results.append(r);print(r.get('package'),len(r.get('dlls',[])),len(r.get('retained',[])),flush=True)
    (OUT/'conda-package-correspondence.json').write_text(json.dumps(results,indent=2))
