from pathlib import Path
import json,sqlite3,zlib
p=Path(__file__).resolve().parent/'validation/3a0b4376378449f1b52402ffb412f546/native-stores/test_generated_two_tee_pressur0/store'
def blob(root):
    files=list((p/'blobs').rglob(root+'*'))
    return json.loads(zlib.decompress(files[0].read_bytes()))
with sqlite3.connect((p/'oma.sqlite3').as_uri()+'?mode=ro',uri=True) as db:
    for identity,status,root in db.execute('select id,status,report_root from candidates order by rowid'):
        report=blob(root)
        for row in report['results']:
            if row['status']!='PASS':
                calc=row.get('witness',{}).get('calculation',{})
                print(json.dumps({'candidate':identity,'status':status,'id':row['id'],'row_status':row['status'],
                    'reason':row['reason'],'calculation_status':calc.get('status'),'calculation_reason':calc.get('reason'),
                    'diagnostics':calc.get('diagnostics'),'witness':row.get('witness',{}) if row['id'] in ('network-pressure-operating-point','network-demand-conditioned-service') else None}))
