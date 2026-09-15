from pathlib import Path
import json,sqlite3,zlib
stage=Path(__file__).resolve().parent
p=stage/'validation/db3afa0073b64ed5aa0da8465e3e0492/native-stores/test_generated_tree_avoids_act0/store'
with sqlite3.connect(p.joinpath('oma.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
    rows=db.execute('select id,status,report_root from candidates order by rowid').fetchall()
    for identity,status,root in rows:
        files=list((p/'blobs').rglob(root+'*'))
        if not files:files=list((p/'blobs'/root[:2]).glob(root[2:]+'*'))
        if not files:print('missing',root);continue
        report=json.loads(zlib.decompress(files[0].read_bytes()))
        print(json.dumps({'candidate':identity,'status':status,'objective':report.get('objective'),
            'non_pass':[{'id':x['id'],'status':x['status'],'reason':x['reason']} for x in report['results'] if x['status']!='PASS']}))
