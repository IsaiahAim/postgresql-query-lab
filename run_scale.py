#!/usr/bin/env python3
"""Run an isolated PostgreSQL lab; only the container created here is removed."""
import json, os, subprocess, time, statistics, uuid, re, argparse, shutil, datetime
from pathlib import Path
ROOT = Path(__file__).resolve().parent
parser = argparse.ArgumentParser(description='Measure a pilot and check capacity before a larger PostgreSQL run.')
parser.add_argument('--rows', type=int, default=500_000_000)
parser.add_argument('--output', default='results-scale')
args = parser.parse_args()
if args.rows < 1_000_000: parser.error('--rows must be at least 1000000')
OUT = ROOT / args.output
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
    print('Loading 1,000,000-row storage pilot...', flush=True)
    (OUT/'setup.txt').write_text(sql(read('01_setup.sql')))
    sql(read('04_index.sql'))
    def size():
        return json.loads(sql("SELECT json_build_object('heap_bytes', pg_table_size('query_lab.transactions'), 'indexes_bytes', pg_indexes_size('query_lab.transactions'), 'total_bytes', pg_total_relation_size('query_lab.transactions'));"))
    pilot = size()
    host_free = shutil.disk_usage(ROOT).free
    container_free = int(command(['docker','exec',NAME,'df','-Pk','/var/lib/postgresql']).splitlines()[-1].split()[3])*1024
    estimated_final = pilot['total_bytes'] * args.rows / 1_000_000
    # 2x measured final relation size plus 15 GiB reserve: planning heuristic, not a guarantee.
    required = int(estimated_final * 2 + 15 * 1024**3)
    blocked = min(host_free, container_free) < required and args.rows > 1_000_000
    capacity = {'recorded_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(), 'target_rows':args.rows, 'pilot_rows':1_000_000, 'pilot_size':pilot, 'host_available_bytes':host_free, 'container_available_bytes':container_free, 'projected_relation_bytes':int(estimated_final), 'required_free_bytes_heuristic':required, 'status':'blocked_insufficient_storage' if blocked else 'capacity_check_passed', 'note':'Projection only; 500 million rows have NOT been loaded if blocked. The multiplier allows rough WAL/index-build headroom; actual demand can differ.'}
    (OUT/'capacity.json').write_text(json.dumps(capacity,indent=2))
    print(json.dumps(capacity,indent=2), flush=True)
    sql('DROP INDEX query_lab.lab_transactions_feed_idx;')
    loaded = 1_000_000
    if not blocked and args.rows > loaded:
        setup = read('01_setup.sql')
        insert = setup[setup.index('INSERT INTO query_lab.transactions'):setup.index('ANALYZE query_lab.accounts')]
        for start in range(loaded+1, args.rows+1, 1_000_000):
            end = min(start+999_999, args.rows)
            available = min(shutil.disk_usage(ROOT).free, int(command(['docker','exec',NAME,'df','-Pk','/var/lib/postgresql']).splitlines()[-1].split()[3])*1024)
            if available < 15*1024**3: raise RuntimeError('Stopped loading: free space is below the 15 GiB reserve')
            sql(insert.replace('generate_series(1::bigint, 1000000::bigint)',f'generate_series({start}::bigint, {end}::bigint)'))
            loaded=end
            print(f'Loaded {loaded:,} rows',flush=True)
        sql('ANALYZE query_lab.transactions;')
    count = int(sql('SELECT count(*) FROM query_lab.transactions;'))
    assert count == loaded
    (OUT/'row-count.txt').write_text(str(count)+'\n')
    env={'version':sql('SELECT version();').strip(),'image':IMAGE,'image_id':command(['docker','inspect','--format','{{.Image}}',NAME]).strip(),'limits':'2 CPUs, 1 GiB memory; Docker local; no published ports','settings':sql("SELECT name,setting,unit FROM pg_settings WHERE name IN ('shared_buffers','work_mem','max_parallel_workers_per_gather');").strip()}
    (OUT/'environment.json').write_text(json.dumps(env,indent=2))
    baseline=query('02_computed.sql'); ranged=query('03_range.sql')
    comparison=[]; expected=None
    for label,q in [('computed',baseline),('range',ranged),('indexed',ranged)]:
        if label=='indexed': sql(read('04_index.sql'))
        sql('EXPLAIN (ANALYZE, BUFFERS) '+q) # unreported warm-up
        plans=[json.loads(sql('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) '+q))[0] for _ in range(5)]
        (OUT/(label+'.json')).write_text(json.dumps(plans,indent=2))
        (OUT/(label+'-explain.txt')).write_text(sql('EXPLAIN (ANALYZE, BUFFERS) '+q))
        actual=rows(q)
        if expected is None: expected=actual
        assert actual==expected, label+' returned different ordered records'
        p=plans[-1]['Plan']
        comparison.append({'version':label,'median_ms':round(statistics.median(x['Execution Time'] for x in plans),3),'runs_ms':[x['Execution Time'] for x in plans],'nodes':[x['Node Type'] for x in nodes(p)],'shared_hits':p.get('Shared Hit Blocks',0),'shared_reads':p.get('Shared Read Blocks',0)})
    full=ranged.replace('\nLIMIT 1000','') if loaded == 1_000_000 else ranged.replace('LIMIT 1000','LIMIT 10000')
    all_rows=rows(full)
    assert len(all_rows)>1000
    walked=[]; cursor=None; pages=0
    while True:
        q=ranged
        if cursor:
            q=q.replace('ORDER BY',"AND (t.created_at, t.id) < (timestamptz '%s', %d)\nORDER BY"%(cursor['created_at'],cursor['id']))
        page=rows(q)
        if not page: break
        if loaded > 1_000_000 and len(walked)>=10000: break
        walked.extend(page); cursor=page[-1]; pages+=1
    assert walked==all_rows, 'Pagination skipped, duplicated or reordered rows'
    ties=sql("SELECT count(*) FROM (SELECT created_at FROM query_lab.transactions GROUP BY created_at HAVING count(*)>1) s;").strip()
    assert int(ties)>0
    # Check every UTC day, including boundaries and days with different filters.
    for day in range(1,31) if loaded == 1_000_000 else []:
        start=f'2026-01-{day:02d}'; end=f'2026-01-{day+1:02d}'
        b=baseline.replace('2026-01-15',start).replace('\nLIMIT 1000','')
        r=re.sub(r'2026-01-(15|16)', lambda m: start if m[1]=='15' else end, full)
        assert rows(b)==rows(r), 'Date equivalence failed on '+start
    sql(read('05_cursor.sql')+"\nEXECUTE lab_next_page ('%s', %d);"%(expected[-1]['created_at'],expected[-1]['id']))
    (OUT/'maintenance.txt').write_text(sql(read('06_maintenance.sql')))
    report={'actual_rows':loaded,'requested_rows':args.rows,'capacity':capacity,'size_after_indexes':size(),'environment':env,'comparison':comparison,'validation':{'ordered_first_page_rows':len(expected),'all_30_days_equivalent':True if loaded == 1_000_000 else 'not tested at this scale','paginated_rows':len(walked),'pages':pages,'timestamp_groups_with_ties':int(ties),'maintenance':'executed successfully'}}
    (OUT/'summary.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2),flush=True)
finally:
    subprocess.run(['docker','rm','-f',NAME],capture_output=True)
