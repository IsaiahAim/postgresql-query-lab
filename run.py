#!/usr/bin/env python3
"""Run an isolated PostgreSQL lab; only the container created here is removed."""
import json, os, subprocess, time, statistics, uuid, re
from pathlib import Path
ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'results'
OUT.mkdir(exist_ok=True)
NAME = 'query-lab-' + uuid.uuid4().hex[:10]
IMAGE = os.environ.get('LAB_IMAGE', 'postgres:18')
def command(args, **kw):
    return subprocess.run(args, check=True, text=True, capture_output=True, **kw).stdout

def sql(source):
    return command(['docker','exec','-i',NAME,'psql','-X','-qAt','-v','ON_ERROR_STOP=1','-U','postgres','-d','lab'], input=source)

def read(name): return (ROOT/'sql'/name).read_text()
def query(name): return read(name).replace('EXPLAIN (ANALYZE, BUFFERS)\n','').strip().rstrip(';')
def rows(q): return json.loads(sql('SELECT coalesce(json_agg(r), \'[]\'::json) FROM ('+q+') r;'))
def nodes(plan):
    yield plan
    for child in plan.get('Plans',[]): yield from nodes(child)
try:
    command(['docker','run','-d','--rm','--name',NAME,'--network','none','--memory','1g','--cpus','2','-e','POSTGRES_HOST_AUTH_METHOD=trust','-e','POSTGRES_DB=lab',IMAGE])
    for _ in range(60):
        try:
            sql('SELECT 1;'); break
        except subprocess.CalledProcessError: time.sleep(1)
    else: raise RuntimeError('PostgreSQL did not become ready')
    (OUT/'setup.txt').write_text(sql(read('01_setup.sql')))
    env={'version':sql('SELECT version();').strip(),'image':IMAGE,'image_id':command(['docker','inspect','--format','{{.Image}}',NAME]).strip(),'limits':'2 CPUs, 1 GiB memory; Docker local; no published ports','settings':sql("SELECT name,setting,unit FROM pg_settings WHERE name IN ('shared_buffers','work_mem','max_parallel_workers_per_gather');").strip()}
    (OUT/'environment.json').write_text(json.dumps(env,indent=2))
    baseline=query('02_computed.sql'); ranged=query('03_range.sql')
    comparison=[]; expected=None
    for label,q in [('computed',baseline),('range',ranged),('indexed',ranged)]:
        if label=='indexed': sql(read('04_index.sql'))
        sql('EXPLAIN (ANALYZE, BUFFERS) '+q) # unreported warm-up
        plans=[json.loads(sql('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) '+q))[0] for _ in range(5)]
        (OUT/(label+'.json')).write_text(json.dumps(plans,indent=2))
        actual=rows(q)
        if expected is None: expected=actual
        assert actual==expected, label+' returned different ordered records'
        p=plans[-1]['Plan']
        comparison.append({'version':label,'median_ms':round(statistics.median(x['Execution Time'] for x in plans),3),'runs_ms':[x['Execution Time'] for x in plans],'nodes':[x['Node Type'] for x in nodes(p)],'shared_hits':p.get('Shared Hit Blocks',0),'shared_reads':p.get('Shared Read Blocks',0)})
    full=ranged.replace('\nLIMIT 1000','')
    all_rows=rows(full)
    assert len(all_rows)>1000
    walked=[]; cursor=None; pages=0
    while True:
        q=ranged
        if cursor:
            q=q.replace('ORDER BY',"AND (t.created_at, t.id) < (timestamptz '%s', %d)\nORDER BY"%(cursor['created_at'],cursor['id']))
        page=rows(q)
        if not page: break
        walked.extend(page); cursor=page[-1]; pages+=1
    assert walked==all_rows, 'Pagination skipped, duplicated or reordered rows'
    ties=sql("SELECT count(*) FROM (SELECT created_at FROM query_lab.transactions GROUP BY created_at HAVING count(*)>1) s;").strip()
    assert int(ties)>0
    # Check every UTC day, including boundaries and days with different filters.
    for day in range(1,31):
        start=f'2026-01-{day:02d}'; end=f'2026-01-{day+1:02d}'
        b=baseline.replace('2026-01-15',start).replace('\nLIMIT 1000','')
        r=re.sub(r'2026-01-(15|16)', lambda m: start if m[1]=='15' else end, full)
        assert rows(b)==rows(r), 'Date equivalence failed on '+start
    sql(read('05_cursor.sql')+"\nEXECUTE lab_next_page ('%s', %d);"%(expected[-1]['created_at'],expected[-1]['id']))
    (OUT/'maintenance.txt').write_text(sql(read('06_maintenance.sql')))
    report={'environment':env,'comparison':comparison,'validation':{'ordered_first_page_rows':len(expected),'all_30_days_equivalent':True,'paginated_rows':len(walked),'pages':pages,'timestamp_groups_with_ties':int(ties),'maintenance':'executed successfully'}}
    (OUT/'summary.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
finally:
    subprocess.run(['docker','rm','-f',NAME],capture_output=True)
