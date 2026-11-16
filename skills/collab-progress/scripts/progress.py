#!/usr/bin/env python3
"""Private progress CLI: collect evidence, accept human/agent review, report counts."""
import argparse
import shutil
import sys
from progress_core import *


def generic_text(value,label,minimum=1,maximum=500):
    if not isinstance(value,str) or not minimum<=len(value)<=maximum:
        raise ValueError(label+' has an invalid length/type')
    if sanitize(value)!=value or re.search(r'https?://|[A-Za-z]:[\\/]|\b\w+\.(?:tsx?|jsx?|json|md|py|php|cs|png|jpe?g|sql)\b',value,re.I):
        raise ValueError(label+' must contain generic prose, not secrets, paths, URLs, or filenames')
    return value


def validate(payload,source,existing=None):
    if not isinstance(payload,dict):
        raise ValueError('Review must be a JSON object')
    rules=rubric()
    if payload.get('schema_version')!=VERSION or payload.get('rubric_version')!=rules['version']:
        raise ValueError('Schema/rubric version mismatch')
    if payload.get('session_id')!=source['session_id']:
        raise ValueError('Wrong source session')
    through=payload.get('reviewed_through_ordinal')
    if not isinstance(through,int) or isinstance(through,bool) or through<0 or through>source_head(source):
        raise ValueError('Invalid reviewed cursor')
    if payload.get('source_revision')!=revision(source,through):
        raise ValueError('Source prefix changed; prepare again. No cursor advanced.')
    if existing and through<existing['reviewed_through_ordinal'] and revision(source,through)!=revision(source,existing['reviewed_through_ordinal']):
        # Moving back is only allowed over events the fingerprint ignores (e.g. maintenance turns).
        raise ValueError('A stale review cannot move the cursor backwards')
    refs={e['ref']:e for e in source['events'] if e['ordinal']<=through}
    parents={k:t['id'] for t in rules['traits'] for k in t['indicators']}
    expected_t={t['id'] for t in rules['traits']}
    old={e['id']:e for e in (existing or {}).get('episodes',[])}
    seen=set();episodes=payload.get('episodes')
    if not isinstance(episodes,list):
        raise ValueError('episodes must be a list')
    if not episodes and not payload.get('exclusion_reason'):
        raise ValueError('Empty sessions require an exclusion reason')
    if episodes and payload.get('exclusion_reason'):
        raise ValueError('Excluded sessions cannot contain episodes')
    if payload.get('exclusion_reason'):
        generic_text(payload['exclusion_reason'],'Exclusion reason')
    for e in episodes:
        if not isinstance(e,dict):
            raise ValueError('Episode must be a JSON object')
        eid=e.get('id','')
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,100}',eid) or eid in seen:
            raise ValueError('Invalid/duplicate stable episode ID')
        seen.add(eid)
        if eid in old and canon(e)==canon(old[eid]):
            continue
        if e.get('baseline') and (eid not in old or not old[eid].get('baseline')):
            raise ValueError('New episodes cannot be marked as baseline')
        lo,hi=e.get('start_ordinal'),e.get('end_ordinal')
        if not all(isinstance(x,int) and not isinstance(x,bool) for x in (lo,hi)) or not 0<=lo<=hi<=through:
            raise ValueError('Episode outside reviewed source prefix')
        if e.get('cohort') not in COHORTS or e.get('work_class') not in CLASSES or not isinstance(e.get('closed'),bool):
            raise ValueError('Invalid cohort, work class, or closed flag')
        if not 8<=len(e.get('summary',''))<=280 or 'REVIEW_REQUIRED' in e['summary']:
            raise ValueError('Generic reviewed episode summary required')
        generic_text(e['summary'],'Episode summary',8,280)
        languages=e.get('languages',[])
        allowed_languages={'typescript','javascript','python','go','rust','java','ruby','php','csharp','swift','kotlin','sql','shell','other'}
        if not isinstance(languages,list) or any(not isinstance(x,str) for x in languages) or len(set(languages))!=len(languages) or not set(languages)<=allowed_languages:
            raise ValueError('Invalid language list')
        codes=e.get('course_episode_ids',[])
        if not isinstance(codes,list) or any(not isinstance(x,str) or not re.fullmatch(r'[A-Za-z0-9-]{1,64}',x) for x in codes) or len(set(codes))!=len(codes):
            raise ValueError('Invalid course episode ID')
        if not isinstance(e.get('traits'),dict) or not isinstance(e.get('indicators'),dict):
            raise ValueError('Traits and indicators must be JSON objects')
        if set(e.get('traits',{}))!=expected_t or set(e.get('indicators',{}))!=set(parents):
            raise ValueError('Each episode needs all 24 traits and 47 indicators')
        for name,j in list(e['traits'].items())+list(e['indicators'].items()):
            if not isinstance(j,dict):
                raise ValueError('Judgment must be a JSON object')
            state=j.get('state')
            if state not in STATES or not isinstance(j.get('verified_outcome'),bool):
                raise ValueError('Invalid judgment state/outcome')
            if j['verified_outcome'] and state!='applied':
                raise ValueError('Verified outcomes must be applied')
            reason=j.get('reason','')
            if not reason or 'REVIEW_REQUIRED' in reason or len(reason)>500:
                raise ValueError('Judgment requires a reviewed reason')
            generic_text(reason,'Judgment reason')
            ev=j.get('evidence_refs',[]);out=j.get('outcome_refs',[])
            if not isinstance(ev,list) or not isinstance(out,list) or any(not isinstance(x,str) for x in ev+out):
                raise ValueError('Evidence/outcome refs must be string arrays')
            if len(set(ev))!=len(ev) or len(set(out))!=len(out):
                raise ValueError('Duplicate evidence reference')
            for ref in ev+out:
                if ref not in refs or not lo<=refs[ref]['ordinal']<=hi:
                    raise ValueError('Evidence reference outside episode/source: '+str(ref))
            if state in ('applied','declined','missed') and not ev:
                raise ValueError('Eligible judgment needs opportunity/evidence references')
            if state in ('applied','declined') and not any(refs[x]['role']=='user' and not refs[x].get('administrative') for x in ev):
                raise ValueError('Applied/declined requires user-originated evidence')
            if j['verified_outcome'] and (not out or not any(refs[x]['role'] in ('tool','user') for x in out)):
                raise ValueError('Independent outcome evidence required')
            if name in parents and state in ('applied','missed','declined') and e['traits'][parents[name]]['state'] in ('ineligible','unobserved'):
                raise ValueError('Eligible indicator requires observed eligible parent')
    ordered=sorted(episodes,key=lambda e:e['start_ordinal'])
    if any(a['end_ordinal']>=b['start_ordinal'] for a,b in zip(ordered,ordered[1:])):
        raise ValueError('Task episodes overlap')
    for obs in payload.get('observations',[]):
        if obs.get('trait_id') not in expected_t or obs.get('episode_id') not in seen:
            raise ValueError('Observation needs a known trait and episode')
        if not 40<=len(obs.get('statement',''))<=280:
            raise ValueError('Observation must be 40-280 characters')
        generic_text(obs['statement'],'Observation',40,280)
        if not obs.get('evidence_refs') or any(x not in refs for x in obs['evidence_refs']):
            raise ValueError('Observation needs real source references')
    if existing and not payload.get('exclusion_reason') and not set(old)<=seen:
        raise ValueError('Existing episodes cannot silently disappear; preserve their stable IDs')
    return payload


def aggregate(reviews,cohort='all',select='all',limit=10):
    episodes=[]
    for review in reviews:
        for e in review['episodes']:
            if cohort=='course' and e['cohort'] not in ('mega-dev','other-course'):
                continue
            if cohort in COHORTS and e['cohort']!=cohort:
                continue
            if select=='new' and e.get('baseline'):
                continue
            episodes.append({**e,'session_id':review['session_id']})
    episodes.sort(key=lambda e:(e.get('start_at_ms',0),e['session_id'],e['start_ordinal']))
    if select in ('recent','previous'):
        complete=[e for e in episodes if e['closed']]
        episodes=complete[-limit:] if select=='recent' else complete[-2*limit:-limit]
    dates=sorted({day for e in episodes for day in e.get('active_dates',[])})
    window_days=(dt.date.fromisoformat(dates[-1])-dt.date.fromisoformat(dates[0])).days+1 if dates else 0
    result=dict(episodes=len(episodes),sessions=len({e['session_id'] for e in episodes}),distinct_active_days=len(dates),window_days=window_days,first_date=dates[0] if dates else None,last_date=dates[-1] if dates else None,traits={},indicators={},work_mix=dict.fromkeys(sorted(CLASSES),0),weekly={},weekly_traits={},languages={})
    for kind in ('traits','indicators'):
        names=[t['id'] for t in rubric()['traits']] if kind=='traits' else [x for t in rubric()['traits'] for x in t['indicators']]
        for name in names:
            counts=dict.fromkeys(COUNTS,0);unknown=0
            for e in episodes:
                j=e[kind][name]
                if j['state'] in ('applied','declined','missed'):
                    counts['eligible']+=1;counts[j['state']]+=1
                    counts['verified_outcome']+=int(j.get('verified_outcome',False))
                elif j['state']=='unobserved':
                    unknown+=1
            denominator=counts['eligible']-counts['declined']
            result[kind][name]=dict(**counts,unobserved=unknown,measurement_status='measured' if counts['eligible']>=3 else 'unmeasured',rate=counts['applied']/denominator if denominator and counts['eligible']>=3 else None)
    for e in episodes:
        result['work_mix'][e['work_class']]+=1
        for language in set(e.get('languages',[])):
            result['languages'][language]=result['languages'].get(language,0)+1
        if e.get('start_at_ms'):
            day=local_date(e['start_at_ms'])
            monday=str(day-dt.timedelta(days=day.weekday()))
            result['weekly'][monday]=result['weekly'].get(monday,0)+1
            weekly=result['weekly_traits'].setdefault(monday,{t['id']:dict.fromkeys(COUNTS,0) for t in rubric()['traits']})
            for tid,j in e['traits'].items():
                if j['state'] in ('applied','declined','missed'):
                    weekly[tid]['eligible']+=1;weekly[tid][j['state']]+=1
                    weekly[tid]['verified_outcome']+=int(j.get('verified_outcome',False))
    for week in result['weekly_traits'].values():
        for c in week.values():
            denominator=c['eligible']-c['declined']
            c['measurement_status']='measured' if c['eligible']>=3 else 'unmeasured'
            c['rate']=c['applied']/denominator if c['eligible']>=3 and denominator else None
    return result


def dashboard(store,cohort='all'):
    reviews=store.all_reviews()
    return dict(schema_version=VERSION,generated_at=now(),privacy='Private local files; no networking or external scoring.',cohort=cohort,baseline=store.setting('baseline_record'),cumulative=aggregate(reviews,cohort),since_baseline=aggregate(reviews,cohort,'new'),recent_10=aggregate(reviews,cohort,'recent'),previous_10=aggregate(reviews,cohort,'previous'),source_cursors={p['session_id']:dict(revision=p['source_revision'],through_ordinal=p['reviewed_through_ordinal']) for p in reviews})


def render(store,cohort='all'):
    from progress_present import preserve_previous_report
    preserve_previous_report(store.root)
    data=dashboard(store,cohort);dest=store.root/'reports'
    suffix='latest' if cohort=='all' else cohort
    atomic_json(dest/(suffix+'.json'),data)
    names={t['id']:t['name'] for t in rubric()['traits']}
    base={x['trait_id']:x['counts'] for x in data['baseline']['traits']}
    def cell(c):
        if c['measurement_status']=='unmeasured':
            return f"unmeasured ({c['eligible']} observed opportunities)"
        return f"{c['applied']} of {c['eligible']}"+(f"; {c['declined']} declined" if c['declined'] else '')
    lines=['# Private collaboration progress','',f"Updated: {data['generated_at']} · Scope: {cohort}",'',f"**{data['cumulative']['episodes']} task episodes in {data['cumulative']['sessions']} chats.** {data['since_baseline']['episodes']} new episodes since the imported baseline.",'','Counts credit visible user actions and directions. Assistant suggestions alone do not count. Missing visibility is unobserved; fewer than three opportunities is unmeasured. Declines are excluded from the rate denominator. No overall skill score is computed.','','Baseline is the immutable all-history snapshot. For course progress, compare recent and previous course tasks; the all-history baseline is not a matched course control.','','| Trait | Original baseline | Current | Since baseline | Recent 10 completed | Previous 10 completed |','|---|---:|---:|---:|---:|---:|']
    for tid,name in names.items():
        c=base[tid];baseline=f"{c['applied']} of {c['eligible']}" if c['eligible'] else 'unmeasured'
        values=[cell(data[k]['traits'][tid]) for k in ('cumulative','since_baseline','recent_10','previous_10')]
        lines.append('| '+tid+' '+name+' | '+baseline+' | '+' | '.join(values)+' |')
    lines+=['',f'## Weekly task volume ({timezone_label()})','','| Week beginning | Episodes |','|---|---:|']
    lines += [f'| {week} | {count} |' for week,count in sorted(data['cumulative']['weekly'].items())]
    trend_traits=['T01','T06','T12','T13','T21','T23']
    lines+=['','## Weekly collaboration trend','','Rates remain unmeasured until three opportunities occur in that week. Full counts for all 24 traits are retained in the JSON report.','','| Week | Goals | Acceptance | Durable decisions | Inspect first | Feedback | Final verification |','|---|---|---|---|---|---|---|']
    for week,values in sorted(data['cumulative']['weekly_traits'].items()):
        lines.append('| '+week+' | '+' | '.join(cell(values[t]) for t in trend_traits)+' |')
    lines+=['','## All indicator counts','','| Indicator | Applied / eligible | Verified | Unobserved |','|---|---:|---:|---:|']
    lines += [f"| {key} | {cell(value)} | {value['verified_outcome']} | {value['unobserved']} |" for key,value in data['cumulative']['indicators'].items()]
    lines+=['','The original assessment, observations, stack, descriptive blocks, and audit remain under `baseline/`. Per-chat evidence, revisions, and cursors live in `progress.sqlite`. A full scan may have pending chats; run `scan` to inspect them. These are not official course scores.','']
    atomic_text(dest/(suffix+'.md'),'\n'.join(lines))
    return dict(report=str(dest/(suffix+'.md')),data=str(dest/(suffix+'.json')))


def scan(store,history):
    pending=[];excluded=[];errors=[]
    existing={p['session_id']:p for p in store.all_reviews()}
    catalog=history.catalog()
    for meta in catalog:
        sid=meta['id']
        if sid in store.excluded():
            excluded.append(dict(session_id=sid,reason=store.excluded()[sid]));continue
        if isinstance(meta['source'],dict) or 'subagent' in str(meta['source']).lower():
            excluded.append(dict(session_id=sid,reason='automated/subagent'));continue
        try:
            source=history.source(sid)
            if not any(e['role']=='user' and not e.get('administrative') for e in source['events']):
                excluded.append(dict(session_id=sid,reason='no task-bearing user messages'));continue
            old=existing.get(sid);rev=revision(source)
            if not old or old['source_revision']!=rev:
                pending.append(dict(session_id=sid,reason='new' if not old else 'changed/reopened',source_revision=rev,through_ordinal=source_head(source),previous_cursor=old['reviewed_through_ordinal'] if old else None))
        except (ValueError,OSError,sqlite3.Error) as error:
            errors.append(dict(session_id=sid,error=str(error)))
    errors=list(history.catalog_errors)+errors
    by_harness={}
    for meta in catalog:by_harness[meta['harness']]=by_harness.get(meta['harness'],0)+1
    return dict(discovered=len(catalog),by_harness=by_harness,pending=pending,excluded=excluded,errors=errors,cursor_advanced=False)


def commit(store,history,payload):
    sid=payload['session_id']
    if sid in store.excluded():
        raise ValueError('This chat is excluded from statistics')
    source=history.source(sid)
    if isinstance(source['meta']['source'],dict) or 'subagent' in str(source['meta']['source']).lower():
        raise ValueError('Automated/subagent histories cannot be committed')
    with store.db:
        store.db.execute('begin immediate')
        old=store.review(sid)
        validate(payload,source,old)
        normalized=json.loads(canon(payload))
        normalized.pop('base_review_revision',None)
        for e in normalized['episodes']:
            if not e.get('start_at_ms'):
                e['start_at_ms']=next((x['timestamp_ms'] for x in source['events'] if x['ordinal']>=e['start_ordinal']),0)
            e['active_dates']=sorted({str(local_date(x['timestamp_ms'])) for x in source['events'] if x['role']=='user' and not x.get('administrative') and e['start_ordinal']<=x['ordinal']<=e['end_ordinal'] and x['timestamp_ms']})
        if old and canon(old)==canon(normalized):
            return dict(status='unchanged',session_id=sid,episodes=len(normalized['episodes']),cursor_advanced=False)
        if 'base_review_revision' not in payload or payload['base_review_revision']!=(digest(old) if old else None):
            raise ValueError('The stored review changed after preparation; prepare again')
        store.db.execute('insert or replace into reviews values (?,?,?,?,?)',(sid,payload['source_revision'],payload['reviewed_through_ordinal'],canon(normalized),now()))
        store.db.execute('insert into audit(at,session_id,action,revision) values (?,?,?,?)',(now(),sid,'replace-session',payload['source_revision']))
        totals=aggregate(store.all_reviews())
        store.db.execute('insert into snapshots(at,totals) values (?,?)',(now(),canon(totals)))
    return dict(status='updated',session_id=sid,episodes=len(payload['episodes']),total_episodes=totals['episodes'],cursor_advanced=True)


def initialize(root,baseline_dir,history,exclude):
    root=Path(root).resolve();baseline_dir=Path(baseline_dir).resolve()
    if (root/'progress.sqlite').exists():
        raise ValueError('Already initialized; never overwrite an existing tracker')
    record=read_json(baseline_dir/'assessment-record.json');ledger=read_json(baseline_dir/'evidence-ledger.json')
    grouped={};sources={}
    for e in ledger['episodes']:
        sid=e['session_id'];n=int(e['id'][1:])
        if sid not in sources:
            sources[sid]=history.source(sid)
        source=sources[sid];users=[x for x in source['events'] if x['role']=='user']
        refs=[x['ref'] for x in users if x['ordinal'] in e['user_evidence_ordinals']]
        fields={}
        for kind,oldkey in [('traits','trait_annotations'),('indicators','indicator_annotations')]:
            fields[kind]={}
            for key,j in ledger[oldkey].items():
                state=next((k for k in ('applied','declined','missed') if n in j[k]),'unobserved' if j.get('reason')=='extraction-gap' else 'ineligible')
                fields[kind][key]=dict(state=state,verified_outcome=n in j['verified_outcome'],evidence_refs=refs if state in ('applied','declined','missed') else [],outcome_refs=[],reason='Imported audited baseline; original evidence ordinals retained in the immutable ledger.')
        hi=e['ordinal_end_exclusive']-1 if e['ordinal_end_exclusive'] is not None else max((x['ordinal'] for x in source['events'] if x['timestamp_ms']<=e['end_ms']),default=source_head(source))
        dates=sorted({str(local_date(x['timestamp_ms'])) for x in users if x['ordinal'] in e['user_evidence_ordinals'] and x['timestamp_ms']})
        episode=dict(id=e['id'],start_ordinal=e['ordinal_first'],end_ordinal=hi,start_at_ms=e['start_ms'],active_dates=dates,closed=True,cohort=e.get('cohort') if e.get('cohort') in COHORTS else 'unclassified',course_episode_ids=list(e.get('course_episode_ids') or []),work_class=e['work_class'],summary=e['label'],languages=e.get('languages_observed_in_tool_events',[]),baseline=True,**fields)
        grouped.setdefault(sid,[]).append(episode)
    reviews=[]
    for sid,episodes in grouped.items():
        source=sources[sid];last=max(e['end_ordinal'] for e in episodes)
        added=[x for x in source['events'] if x['role']=='user' and not x.get('administrative') and x['ordinal']>last]
        through=last if added else source_head(source)
        reviews.append(dict(schema_version=VERSION,rubric_version=rubric()['version'],session_id=sid,source_revision=revision(source,through),reviewed_through_ordinal=through,exclusion_reason=None,episodes=episodes,observations=[]))
    totals=aggregate(reviews)
    if totals['episodes']!=record['coverage']['task_episodes']:
        raise ValueError('Baseline task count mismatch')
    for kind,idkey in [('traits','trait_id'),('indicators','indicator_id')]:
        for row in record[kind]:
            if row['measurement_status']=='measured' and any(totals[kind][row[idkey]][k]!=v for k,v in row['counts'].items()):
                raise ValueError('Baseline counts do not reconcile: '+row[idkey])
    # Source inspection and count validation precede creation of persistent state.
    make_private_dir(root)
    store=Store(root,write=True,create=True)
    try:
        with store.db:
            for value in reviews:
                store.db.execute('insert into reviews values (?,?,?,?,?)',(value['session_id'],value['source_revision'],value['reviewed_through_ordinal'],canon(value),now()))
            dest=root/'baseline';dest.mkdir(parents=True,exist_ok=True);manifest={}
            for path in baseline_dir.iterdir():
                if path.is_file() and path.suffix in ('.json','.md'):
                    content=path.read_bytes();manifest[path.name]=hashlib.sha256(content).hexdigest()
                    shutil.copyfile(path,dest/path.name)
            store.put_setting('baseline_record',record);store.put_setting('baseline_manifest',manifest)
            store.put_setting('history_homes',history.homes_setting());store.put_setting('excluded_sessions',{sid:'assessment/tracker development conversation' for sid in exclude})
            store.put_setting('privacy',dict(network_enabled=False,upload_enabled=False));store.put_setting('initialized_at',now())
            store.db.execute('insert into audit(at,action) values (?,?)',(now(),'import-baseline'))
            store.db.execute('insert into snapshots(at,totals) values (?,?)',(now(),canon(totals)))
    except Exception:
        store.db.close()
        (root/'progress.sqlite').unlink(missing_ok=True)
        raise
    try:
        return dict(status='initialized',episodes=totals['episodes'],sessions=totals['sessions'],**render(store))
    finally:
        store.db.close()


def initialize_empty(root,history,exclude):
    """Fresh tracker: zero baseline, no imported episodes. Never overwrites."""
    root=Path(root).resolve()
    if (root/'progress.sqlite').exists():
        raise ValueError('Already initialized; never overwrite an existing tracker')
    zero=dict.fromkeys(COUNTS,0)
    record=dict(source='Fresh multi-harness tracker with a zero baseline.',coverage=dict(task_episodes=0,sessions=0),
                traits=[dict(trait_id=t['id'],measurement_status='unmeasured',counts=dict(zero)) for t in rubric()['traits']],
                indicators=[dict(indicator_id=i,measurement_status='unmeasured',counts=dict(zero)) for t in rubric()['traits'] for i in t['indicators']])
    make_private_dir(root)
    store=Store(root,write=True,create=True)
    try:
        with store.db:
            store.put_setting('baseline_record',record);store.put_setting('baseline_manifest',{})
            store.put_setting('history_homes',history.homes_setting());store.put_setting('excluded_sessions',{sid:'assessment/tracker development conversation' for sid in exclude})
            store.put_setting('privacy',dict(network_enabled=False,upload_enabled=False));store.put_setting('initialized_at',now())
            store.db.execute('insert into audit(at,action) values (?,?)',(now(),'init-empty'))
            store.db.execute('insert into snapshots(at,totals) values (?,?)',(now(),canon(aggregate([]))))
        return dict(status='initialized',episodes=0,sessions=0,**render(store))
    finally:
        store.db.close()


def python_info():
    return dict(executable=sys.executable,version='.'.join(map(str,sys.version_info[:3])),ok=sys.version_info>=(3,11))


def where(history):
    path,how=locate_data()
    exists=bool(path and (path/'progress.sqlite').exists())
    return dict(configured=path is not None,data_dir=str(path) if path else None,chosen_by=how,config=str(CONFIG_PATH),
                default_data_dir=str(DEFAULT_DATA),coaching_dir=str(path/'coaching') if path else None,tracker_exists=exists,
                private=True,python=python_info(),harness_homes={k:dict(path=str(v),found=v.is_dir()) for k,v in history.homes.items()},
                next_step=None if exists else ('ask the user where to store private data (default '+str(DEFAULT_DATA)+'), then run setup --data PATH'))


def copy_tracker(source,target):
    """Copy an existing tracker folder; the database goes through SQLite's backup API. The source is opened read-only."""
    import sqlite3 as sql
    source=Path(source).expanduser().resolve()
    if not (source/'progress.sqlite').exists():
        raise ValueError('No tracker to copy at '+str(source))
    for item in source.iterdir():
        if item.name.startswith('progress.sqlite'):continue
        dest=target/item.name
        if item.is_dir():shutil.copytree(item,dest,dirs_exist_ok=True)
        elif not dest.exists():shutil.copy2(item,dest)
    src=sql.connect((source/'progress.sqlite').as_uri()+'?mode=ro',uri=True)
    out=sql.connect(target/'progress.sqlite')
    try:src.backup(out)
    finally:src.close();out.close()


def setup(target,copy_from,history):
    """Record the user's chosen data folder; create it privately; copy, reuse or start a tracker there."""
    target=Path(target).expanduser().resolve()
    if copy_from and (target/'progress.sqlite').exists():
        raise ValueError('Target already holds a tracker; refusing to overwrite it with --copy-from')
    if target.exists() and not (target/'progress.sqlite').exists():
        foreign=[x.name for x in target.iterdir() if x.name not in ('.gitignore','PRIVATE.txt')]
        if foreign and not copy_from:
            raise ValueError('Target folder is not empty and holds no tracker: '+str(target))
    make_private_dir(target)
    if (target/'progress.sqlite').exists():action='reused existing tracker'
    elif copy_from:copy_tracker(copy_from,target);action='copied tracker from '+str(Path(copy_from).expanduser().resolve())
    else:action=None
    (target/'coaching').mkdir(exist_ok=True)
    write_config(target)
    if action is None:
        initialize_empty(target,history,[]);action='started a new empty tracker'
    return dict(status='configured',action=action,data_dir=str(target),config=str(CONFIG_PATH),coaching_dir=str(target/'coaching'),private=True)


def history_homes(overrides,stored=None):
    """Stored homes, then defaults for any harness not stored, then CLI overrides."""
    registry=adapters()
    homes={name:m.default_home() for name,m in registry.items()}
    homes.update({k:Path(v) for k,v in (stored or {}).items()})
    for item in overrides:
        name,_,path=item.partition('=')
        if harness_of(name) not in registry or not path:
            raise ValueError('--history-home expects HARNESS[:LABEL]=PATH with HARNESS in '+', '.join(registry))
        homes[name]=Path(path).expanduser()
    return homes


def manage_homes(store,add,remove):
    """Persist extra transcript homes, e.g. codex:work=~/.codex_work from a T3 Code provider instance."""
    registry=adapters();homes=dict(store.setting('history_homes',{}) or {})
    for item in add:
        key,_,path=item.partition('=')
        if harness_of(key) not in registry or not path:
            raise ValueError('--add expects HARNESS[:LABEL]=PATH with HARNESS in '+', '.join(registry))
        path=Path(path).expanduser().resolve()
        if not path.is_dir():
            raise ValueError('Not a folder: '+str(path))
        homes[key]=str(path)
    for key in remove:
        if key not in homes:
            raise ValueError('No stored home named '+key)
        if key in registry:
            raise ValueError('Built-in default home '+key+' cannot be removed; point it elsewhere with --add '+key+'=PATH')
        homes.pop(key)
    if add or remove:
        with store.db:
            store.put_setting('history_homes',homes)
            store.db.execute('insert into audit(at,action) values (?,?)',(now(),'homes: +'+','.join(add)+' -'+','.join(remove)))
    return dict(homes=homes,effective={k:str(v) for k,v in history_homes([],homes).items()})


def history_source_only(args):
    return History(history_homes(args.history_home)).source(resolve_session(args.session))


def resolve_session(sid):
    value=next((os.environ[k] for m in adapters().values() for k in m.SESSION_ENV if os.environ.get(k)),None) if sid=='current' else sid
    if not value:
        raise ValueError('No current session ID; use an actual ID from the environment or scan output')
    return value


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data',type=Path,help='Use this tracker folder for one command (overrides config)');p.add_argument('--history-home',action='append',default=[],metavar='HARNESS=PATH',help='Override a transcript home, e.g. codex=~/.codex (repeatable)')
    sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('where',help='Show the configured private data folder, defaults, Python and harness homes')
    sub.add_parser('doctor',help='Diagnose this environment: harness, homes, adapters, skills; list steps for the agent and the human')
    q=sub.add_parser('probe',help='Describe the structure of an unknown transcript store (no message text)');q.add_argument('path',type=Path)
    q=sub.add_parser('home',help='List, add or remove transcript homes stored in the tracker');q.add_argument('--add',action='append',default=[],metavar='HARNESS[:LABEL]=PATH');q.add_argument('--remove',action='append',default=[],metavar='KEY')
    q=sub.add_parser('setup',help='Choose the private data folder (first run)');g=q.add_mutually_exclusive_group(required=True);g.add_argument('--data',dest='target',type=Path);g.add_argument('--default',action='store_true',help='Use SKILL_DIR/data');q.add_argument('--copy-from',type=Path,help='Copy an existing tracker folder into the new location')
    q=sub.add_parser('init');g=q.add_mutually_exclusive_group(required=True);g.add_argument('--baseline',type=Path);g.add_argument('--empty',action='store_true',help='Start a fresh tracker with a zero baseline');q.add_argument('--exclude-session',action='append',default=[])
    q=sub.add_parser('scan');q.add_argument('--output',type=Path)
    q=sub.add_parser('prepare');q.add_argument('--session',default='current');q.add_argument('--output',type=Path,required=True)
    q=sub.add_parser('context');q.add_argument('--session',default='current');q.add_argument('--before-ordinal',type=int)
    q=sub.add_parser('read-event');q.add_argument('--session',default='current');q.add_argument('--ref',required=True)
    q=sub.add_parser('commit');q.add_argument('--file',type=Path,required=True)
    q=sub.add_parser('report');q.add_argument('--cohort',choices=['all','course']+sorted(COHORTS),default='all')
    sub.add_parser('snapshot',help='Save one immutable invocation report and refresh the offline dashboard')
    sub.add_parser('dashboard',help='Rebuild the offline dashboard without adding a snapshot')
    sub.add_parser('status');args=p.parse_args(argv)
    try:
        if args.command=='where':
            result=where(History(history_homes(args.history_home)))
        elif args.command=='probe':
            from doctor import probe
            result=probe(args.path)
        elif args.command=='doctor':
            from doctor import doctor
            path,_=locate_data();stored=None
            if args.data or (path and (path/'progress.sqlite').exists()):
                tracker=Store(args.data or path);stored=tracker.setting('history_homes');tracker.db.close()
            result=doctor(History(history_homes(args.history_home,stored)),python_info(),resolve_session)
        elif args.command=='setup':
            result=setup(DEFAULT_DATA if args.default else args.target,args.copy_from,History(history_homes(args.history_home)))
        elif args.command in ('context','read-event') and not args.data and locate_data()[0] is None:
            # Coaching can read the transcript before any tracker exists.
            source=history_source_only(args)
            result=packet(source,args.before_ordinal) if args.command=='context' else next((x for x in packet(source,limit=1000000)['events'] if x['ref']==args.ref),None)
            if result is None:raise ValueError('Reference not found')
        elif args.command=='init':
            history=History(history_homes(args.history_home))
            root=args.data or data_path()
            result=initialize_empty(root,history,args.exclude_session) if args.empty else initialize(root,args.baseline,history,args.exclude_session)
        else:
            store=Store(args.data or data_path(),write=args.command=='commit')
            history=History(history_homes(args.history_home,store.setting('history_homes')))
            if args.command=='scan':
                result=scan(store,history)
                if args.output:atomic_json(args.output,result)
            elif args.command=='prepare':
                result=prepare(store,history,resolve_session(args.session));atomic_json(args.output,result)
                result=dict(packet=str(args.output),session_id=result['context']['session_id'],source_revision=result['context']['source_revision'],cursor_advanced=False)
            elif args.command in ('context','read-event'):
                source=history.source(resolve_session(args.session))
                if args.command=='context':result=packet(source,args.before_ordinal)
                else:
                    result=next((x for x in packet(source,limit=1000000)['events'] if x['ref']==args.ref),None)
                    if result is None:raise ValueError('Reference not found')
            elif args.command=='home':
                store.db.close();store=Store(args.data or data_path(),write=bool(args.add or args.remove))
                result=manage_homes(store,args.add,args.remove)
            elif args.command=='commit':
                result=commit(store,history,read_json(args.file));result.update(render(store))
            elif args.command=='report':result=render(store,args.cohort)
            elif args.command=='snapshot':
                from progress_present import SCOPES, create_snapshot
                result=create_snapshot(store.root,{cohort:dashboard(store,cohort) for cohort in SCOPES})
            elif args.command=='dashboard':
                from progress_present import refresh_viewer
                result=dict(dashboard=refresh_viewer(store.root),scoring_unchanged=True)
            else:result=dict(data_root=str(store.root),counts=aggregate(store.all_reviews()),privacy=store.setting('privacy'),excluded_sessions=store.excluded())
        print(json.dumps(result,ensure_ascii=False,indent=2));return 0
    except NotConfigured as error:
        print(json.dumps(dict(error=str(error),needs_setup=True,default_data_dir=str(DEFAULT_DATA),cursor_advanced=False),ensure_ascii=False),file=sys.stderr);return 2
    except (ValueError,OSError,sqlite3.Error,KeyError,TypeError) as error:
        print(json.dumps(dict(error=str(error),cursor_advanced=False),ensure_ascii=False),file=sys.stderr);return 1
    finally:
        if 'store' in locals():
            store.db.close()


if __name__=='__main__':
    sys.exit(main())
