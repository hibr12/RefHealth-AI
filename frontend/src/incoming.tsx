import {useEffect,useState} from 'react';
import {Link,Navigate} from 'react-router-dom';
import {useQuery,useQueryClient} from '@tanstack/react-query';
import {AlertTriangle,Clock,RefreshCw} from 'lucide-react';
import {useAuth} from './auth';
import {get,post,errorMessage} from './api';
import {Heading,Status,Empty,Form,Action} from './ui';
import './incoming.css';

const levels=['CRITICAL','HIGH','MEDIUM','LOW'];
const policies=[...levels,'REVIEW_REQUIRED'];
export function hospitalTime(value:string|null,timezone:string){return value?new Intl.DateTimeFormat('en-GB',{timeZone:timezone,dateStyle:'medium',timeStyle:'medium'}).format(new Date(value)):'Unknown';}
export function arrivalFilterUtc(value:string,timezone:string){
  // Interpret the local datetime input in the hospital timezone, not the viewer's device timezone.
  const target=new Date(value+'Z').getTime();let instant=target;
  const formatter=new Intl.DateTimeFormat('en-CA',{timeZone:timezone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'});
  for(let n=0;n<3;n++){const p=Object.fromEntries(formatter.formatToParts(new Date(instant)).map(p=>[p.type,p.value]));const local=Date.parse(`${p.year}-${p.month}-${p.day}T${p.hour}:${p.minute}:${p.second}Z`);instant+=target-local;}
  return new Date(instant).toISOString();
}
export function waitLabel(seconds:number|null){if(seconds===null)return 'Unknown arrival time';const minutes=Math.floor(Math.max(0,seconds)/60);return minutes>=1440?`${Math.floor(minutes/1440)}d ${Math.floor(minutes%1440/60)}h ${minutes%60}m`:minutes>=60?`${Math.floor(minutes/60)}h ${minutes%60}m`:`${minutes}m ${Math.floor(seconds%60)}s`;}
export function PriorityBadge({priority}:{priority:string|null}){return <span className={`queue-priority priority-${(priority??'review').toLowerCase()}`}>{priority==='CRITICAL'?'!! ':priority==='HIGH'?'! ':''}{priority??'CLINICAL REVIEW REQUIRED'}</span>;}

function Audit({id,timezone}:{id:string;timezone:string}){
  const [page,setPage]=useState(1);
  const q=useQuery({queryKey:['incoming-events',id,page],queryFn:()=>get(`/incoming/${id}/events?page=${page}`),refetchInterval:10000});
  return <div className="queue-audit"><h3>Queue audit history</h3><Status query={q}/>{q.data?.events.map((event:any)=><article key={event.id}><strong>{event.kind.replaceAll('_',' ')}</strong><small>{hospitalTime(event.createdAt,timezone)} · {event.actorId?`Staff ID ${event.actorId}`:'System monitor'}</small><p>{event.reason}</p>{(event.priority||event.previousPriority)&&<p>{event.previousPriority??'Unassigned'} → {event.priority??'No recommendation'}</p>}<details><summary>Recorded evidence</summary><pre>{JSON.stringify(event.details,null,2)}</pre></details></article>)}<div className="queue-pagination"><button className="secondary" disabled={page===1} onClick={()=>setPage(page-1)}>Previous events</button><span>Page {page}</span><button className="secondary" disabled={!q.data||page*50>=q.data.total} onClick={()=>setPage(page+1)}>Older events</button></div></div>;
}

function QueuePolicy({policy}:{policy:any}){
  const cache=useQueryClient(),[error,setError]=useState(''),[message,setMessage]=useState(''),[busy,setBusy]=useState(false);
  return <details className="panel queue-policy"><summary>Hospital queue policy</summary><p>Deadlines are hospital operational policies, not clinical urgency. Blank deadlines disable monitoring for that category. Changes apply to new arrivals; existing referrals keep their recorded policy.</p>
    <form key={policy.version} onSubmit={async e=>{e.preventDefault();const data=new FormData(e.currentTarget);setError('');setMessage('');setBusy(true);try{
      const deadlines=Object.fromEntries(policies.filter(p=>String(data.get(`${p}-minutes`)).trim()).map(p=>[p,{minutes:Number(data.get(`${p}-minutes`)),warningMinutes:Number(data.get(`${p}-warning`))}]));
      const protocolText=String(data.get('protocol')||'').trim();
      await post('/incoming/policy',{version:policy.version,timezone:data.get('timezone'),emergencyProcedure:data.get('emergencyProcedure'),deadlines,protocol:protocolText?JSON.parse(protocolText):null});
      await cache.invalidateQueries();setMessage('Queue policy saved for future arrivals.');
    }catch(err){setError(err instanceof SyntaxError?'Protocol must be valid JSON.':errorMessage(err));}finally{setBusy(false);}}}>
      <label>Receiving hospital timezone<input name="timezone" required defaultValue={policy.timezone}/></label>
      <div className="table-wrap"><table><thead><tr><th>Confirmed priority</th><th>Acknowledge within (minutes)</th><th>Warn before deadline (minutes)</th></tr></thead><tbody>{policies.map(p=><tr key={p}><td>{p.replaceAll('_',' ')}</td><td><input aria-label={`${p} deadline minutes`} name={`${p}-minutes`} type="number" min="1" max="525600" defaultValue={policy.deadlines[p]?.minutes??''}/></td><td><input aria-label={`${p} warning minutes`} name={`${p}-warning`} type="number" min="0" max="525600" defaultValue={policy.deadlines[p]?.warningMinutes??0}/></td></tr>)}</tbody></table></div>
      <label>Approved emergency escalation procedure<textarea name="emergencyProcedure" rows={3} maxLength={4000} defaultValue={policy.emergencyProcedure}/></label>
      <details><summary>Future clinical protocol integration</summary><p>Automatic clinical recommendations are disabled while no approved protocol is configured. Upload only an officially approved, clinically validated protocol with its approval authority, date, source, and clinical validation reference. Recommendations always require clinician confirmation before they affect queue order.</p><label>Approved protocol JSON (leave blank to disable)<textarea name="protocol" rows={8} defaultValue={policy.protocol?JSON.stringify(policy.protocol,null,2):''}/></label></details>
      {error&&<p role="alert" className="error">{error}</p>}{message&&<p role="status" className="success">{message}</p>}<button disabled={busy}>{busy?'Saving…':'Save hospital queue policy'}</button>
    </form>
  </details>;
}

function ReferralCard({referral:r,timezone,now,canTriage,policy}:{referral:any;timezone:string;now:number;canTriage:boolean;policy:any}){
  const [expanded,setExpanded]=useState(false);
  const active=['SUBMITTED','ACCEPTED','IN_PROGRESS'].includes(r.status);
  const waiting=r.receivedAt?Math.max(0,((r.acknowledgedAt?new Date(r.acknowledgedAt).getTime():active?now:new Date(r.updatedAt).getTime())-new Date(r.receivedAt).getTime())/1000):null;
  const overdue=!r.acknowledgedAt&&r.status==='SUBMITTED'&&r.acknowledgementDueAt&&now>=new Date(r.acknowledgementDueAt).getTime();
  const warning=!overdue&&!r.acknowledgedAt&&r.status==='SUBMITTED'&&r.acknowledgementWarningAt&&now>=new Date(r.acknowledgementWarningAt).getTime();
  const emergency=r.urgency==='Emergency'||r.confirmedPriority==='CRITICAL';
  return <article className={`queue-card ${overdue?'queue-overdue':''}`}>
    <div className="queue-card-heading"><div><PriorityBadge priority={r.confirmedPriority}/><h2><Link to={`/referrals/${r.id}`}>{r.patient.name}</Link></h2><small>{r.patient.identifier} · {r.patient.age} years · {r.patient.sex}</small></div><div className="queue-wait"><Clock size={17}/><strong>{waitLabel(waiting)}</strong><small>{r.acknowledgedAt?'Wait until acknowledged':active?'Waiting since arrival':'Wait at closure'}</small></div></div>
    <p className="queue-id">Referral {r.id}</p><div className="queue-facts"><div><small>Referring facility</small><strong>{r.origin.name}</strong></div><div><small>Required service / specialty</small><strong>{r.requiredService}{r.requiredSpecialty?` / ${r.requiredSpecialty}`:''}</strong></div><div><small>Submitted</small><strong title={r.submittedAt??''}>{hospitalTime(r.submittedAt,timezone)}</strong></div><div><small>Received at this hospital</small><strong title={r.receivedAt??''}>{hospitalTime(r.receivedAt,timezone)}</strong></div><div><small>Referral status</small><strong>{r.status.replaceAll('_',' ')}</strong></div><div><small>Acknowledgement</small><strong>{r.acknowledgedAt?hospitalTime(r.acknowledgedAt,timezone):'Not acknowledged'}</strong></div><div><small>Acknowledgement deadline</small><strong>{r.acknowledgementDueAt?hospitalTime(r.acknowledgementDueAt,timezone):r.receivedAt?'No configured deadline':'Unknown arrival time'}</strong></div><div><small>Operational escalation</small><strong>{overdue?'OVERDUE':warning?'DEADLINE APPROACHING':r.overdueNotifiedAt?'Overdue alert recorded':r.warningNotifiedAt?'Warning recorded':'No escalation'}</strong></div></div>
    {(overdue||warning)&&<p className="queue-warning"><AlertTriangle size={18}/>{overdue?'Acknowledgement overdue.':'Acknowledgement deadline approaching.'} Follow the hospital escalation policy. Clinical priority is unchanged.</p>}
    {emergency&&<p className="queue-warning"><AlertTriangle size={18}/>Emergency escalation: {policy.emergencyProcedure||'Follow your hospital’s approved emergency procedure; contact the responsible clinical team immediately.'}</p>}
    {!r.receivedAt&&<p className="notice">This historical referral has no recorded receipt timestamp. Arrival and waiting time have not been estimated.</p>}
    <div className="queue-advice"><strong>Clinician-assessed urgency: {r.urgency}</strong><p>AI / protocol recommendation: {r.aiPriority??(r.assessmentStatus==='DISABLED'?'Disabled — no approved protocol':'No recommendation')}</p><p>{r.priorityExplanation}</p>{!r.confirmedPriority&&<p><strong>Awaiting clinician assignment. This referral has no confirmed queue priority.</strong></p>}</div>
    <details><summary>Operational predictions (do not determine clinical priority)</summary><p>Acknowledgement-delay prediction: {typeof r.delayPrediction?.result?.delay_probability==='number'?`${(r.delayPrediction.result.delay_probability*100).toFixed(1)}% estimated delay risk`:'Unavailable; no saved prediction for this receiving hospital.'}</p>{r.delayPrediction&&<small>Recorded {hospitalTime(r.delayPrediction.createdAt,timezone)}</small>}</details>
    <div className="queue-actions">{!r.acknowledgedAt&&r.status==='SUBMITTED'&&<Action path={`/incoming/${r.id}/acknowledge`} body={{version:r.version}}>Acknowledge receipt</Action>}<Link className="button secondary" to={`/referrals/${r.id}`}>Open referral workflow</Link><button className="secondary" aria-expanded={expanded} onClick={()=>setExpanded(!expanded)}>{expanded?'Close review & audit':'Review priority & audit'}</button></div>
    {expanded&&<div className="queue-review"><h3>Clinical information</h3><p>{r.clinicalSummary}</p>{r.clinicalObservations&&<pre>{JSON.stringify(r.clinicalObservations,null,2)}</pre>}{canTriage&&active?<><h3>Assign or confirm clinical priority</h3><Form fields={[{name:'priority',label:'Clinician-confirmed priority',type:'select',options:levels},{name:'reason',label:'Clinical review / change reason',type:'textarea'}]} label="Save confirmed priority" onSubmit={v=>post(`/incoming/${r.id}/priority`,{...v,version:r.version})}/>{policy.protocol&&<Action path={`/incoming/${r.id}/recommendation`} body={{version:r.version}}>Request approved protocol recommendation</Action>}</>:active?<p>Clinical priority review permission is required to assign or change priority.</p>:null}<Audit id={r.id} timezone={timezone}/></div>}
  </article>;
}

export function IncomingQueue(){
  const {user}=useAuth(),[filters,setFilters]=useState<Record<string,string>>({sort:'priority'}),[page,setPage]=useState(1),[clock,setClock]=useState(Date.now());
  const allowed=user?.role==='HOSPITAL_ADMIN'||!!user?.permissions?.includes('REFERRAL_RECEIVE');
  const canTriage=allowed&&!!user?.permissions?.includes('REFERRAL_TRIAGE');
  const [timezone,setTimezone]=useState('Africa/Nairobi');
  const params=new URLSearchParams({...Object.fromEntries(Object.entries(filters).filter(([,v])=>v).map(([k,v])=>[k,k==='arrivedFrom'||k==='arrivedTo'?arrivalFilterUtc(v+(k==='arrivedTo'?':59':':00'),timezone):v])),page:String(page),limit:'20'});
  const q=useQuery({queryKey:['incoming',params.toString()],queryFn:()=>get(`/incoming?${params}`),enabled:allowed,refetchInterval:10000});
  useEffect(()=>{const id=setInterval(()=>setClock(Date.now()),1000);return()=>clearInterval(id);},[]);
  useEffect(()=>{if(q.data?.policy.timezone)setTimezone(q.data.policy.timezone);},[q.data?.policy.timezone]);
  const now=q.data?new Date(q.data.serverTime).getTime()+Math.max(0,clock-q.dataUpdatedAt):clock;
  function filter(key:string,value:string){setFilters(v=>({...v,[key]:value}));setPage(1);}
  if(!allowed)return <Navigate to="/unauthorized" replace/>;
  const d=q.data;
  return <><Heading title="Incoming referrals" sub="Clinician-confirmed priority first. Earliest receiving-hospital arrival first within each priority." action={<button className="secondary" disabled={q.isFetching} onClick={()=>void q.refetch()}><RefreshCw size={16}/>Refresh queue</button>}/>
    <p className="muted">Updates automatically every 10 seconds. All timestamps use {d?.policy.timezone??'the receiving hospital timezone'}.</p>
    {d&&<><div className="queue-summary"><strong>{d.total} matching referrals</strong><button className="secondary" onClick={()=>{setFilters({sort:'priority',review:'true'});setPage(1);}}><AlertTriangle size={17}/>{d.unreviewed} active referrals need clinical priority review</button></div>
      {!d.policy.protocol&&<p className="notice">Automatic clinical priority recommendations are disabled. An authorized clinician must assign and confirm priority. No approved, clinically validated protocol has been supplied.</p>}
      {user?.role==='HOSPITAL_ADMIN'&&<QueuePolicy policy={d.policy}/>}</>}
    <section className="panel queue-filters" aria-label="Incoming referral filters">
      <label>Confirmed clinical priority<select value={filters.priority??''} onChange={e=>filter('priority',e.target.value)}><option value="">All priorities</option>{levels.map(p=><option key={p}>{p}</option>)}<option value="REVIEW_REQUIRED">Unassigned — clinical review required</option></select></label>
      <label>Referring facility<select value={filters.originId??''} onChange={e=>filter('originId',e.target.value)}><option value="">All facilities</option>{d?.facilities.map((f:any)=><option value={f.id} key={f.id}>{f.name}</option>)}</select></label>
      <label>Required service<select value={filters.service??''} onChange={e=>filter('service',e.target.value)}><option value="">All services</option>{d?.services.map((s:string)=><option key={s}>{s}</option>)}</select></label>
      <label>Referral status<select value={filters.status??''} onChange={e=>filter('status',e.target.value)}><option value="">Active referrals</option>{['SUBMITTED','ACCEPTED','IN_PROGRESS','COMPLETED','REJECTED','CANCELLED','ALL'].map(s=><option key={s}>{s}</option>)}</select></label>
      <label>Acknowledgement<select value={filters.acknowledged??''} onChange={e=>filter('acknowledged',e.target.value)}><option value="">All</option><option value="no">Not acknowledged</option><option value="yes">Acknowledged</option></select></label>
      <label>Sort queue<select value={filters.sort} onChange={e=>filter('sort',e.target.value)}><option value="priority">Confirmed priority, then earliest arrival</option><option value="arrival">Earliest arrival (all priorities)</option><option value="waiting">Longest unacknowledged wait</option></select></label>
      <label>Arrived from ({timezone})<input type="datetime-local" value={filters.arrivedFrom??''} onChange={e=>filter('arrivedFrom',e.target.value)}/></label>
      <label>Arrived through ({timezone})<input type="datetime-local" value={filters.arrivedTo??''} onChange={e=>filter('arrivedTo',e.target.value)}/></label>
      <label>Unacknowledged wait, at least (minutes)<input type="number" min="0" max="5256000" value={filters.minWaitingMinutes??''} onChange={e=>filter('minWaitingMinutes',e.target.value)}/></label>
      <label className="queue-check"><input type="checkbox" checked={filters.overdue==='true'} onChange={e=>filter('overdue',e.target.checked?'true':'')}/>Overdue only</label><label className="queue-check"><input type="checkbox" checked={filters.review==='true'} onChange={e=>filter('review',e.target.checked?'true':'')}/>Clinical review required</label><button className="secondary" onClick={()=>{setFilters({sort:'priority'});setPage(1);}}>Clear filters</button>
    </section>
    {filters.sort!=='priority'&&<p className="notice">Alternative operational view: sorted by arrival time. Return to priority sorting to see the clinical queue.</p>}
    <Status query={q}/>{d?.referrals.length===0&&<Empty>No incoming referrals match these filters.</Empty>}
    {d?.referrals.map((r:any)=><ReferralCard key={r.id} referral={r} timezone={d.policy.timezone} policy={d.policy} now={now} canTriage={canTriage}/>)}
    {d&&<><div className="queue-pagination"><button className="secondary" disabled={page===1} onClick={()=>setPage(page-1)}>Previous page</button><span>Page {page} of {Math.max(1,Math.ceil(d.total/20))}</span><button className="secondary" disabled={page*20>=d.total} onClick={()=>setPage(page+1)}>Next page</button></div><details className="panel"><summary>Hospital workload forecast — operational planning only</summary><p>Workload does not determine or lower clinical priority.</p>{d.workloadPrediction?<><p>{d.workloadPrediction.result.forecast_date}: {d.workloadPrediction.result.predicted_workload??'Unavailable'} predicted workload</p><small>Recorded {hospitalTime(d.workloadPrediction.createdAt,d.policy.timezone)}</small>{d.workloadPrediction.result.limitations?.map((note:string)=><p key={note}>{note}</p>)}</>:<p>No workload forecast is available. Use AI intelligence after recording sufficient verified daily observations.</p>}<Link to="/intelligence">Open operational intelligence</Link></details></>}
  </>;
}
