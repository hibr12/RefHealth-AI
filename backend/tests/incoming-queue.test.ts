import {test,before,after} from 'node:test';
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {buildApp,db} from '../src/app.js';
import {hashPassword} from '../src/security.js';
import {config} from '../src/config.js';
import {assessReferral,monitorAcknowledgements,deadlineFields,queueTiming} from '../src/incoming-queue.js';

if(!process.env.DATABASE_URL?.includes('coecare_test'))throw Error('Use isolated coecare_test only.');
const suffix=randomUUID(),password='Queue-test-password-123!';
let app:Awaited<ReturnType<typeof buildApp>>,origin:string,destination:string,other:string,patient:string;
const tokens:Record<string,string>={},ids:Record<string,string>={};
const syntheticProtocol={name:'TEST ONLY categorical protocol',version:'test-1',reference:'Synthetic test fixture, not a clinical protocol',clinicalValidationReference:'TEST ONLY simulated approval evidence',approvedBy:'Synthetic test reviewer',approvedAt:'2026-01-01T00:00:00Z',approvalAttested:true,requiredFields:['urgency'],rules:[{id:'test-emergency',priority:'CRITICAL',explanation:'Synthetic test rule only.',conditions:[{field:'urgency',operator:'equals',value:'Emergency'}]}]};
async function req(method:any,url:string,payload?:any,who='receiver'){const response=await app.inject({method,url,payload,headers:tokens[who]?{authorization:`Bearer ${tokens[who]}`}:{}});return {status:response.statusCode,data:response.json()};}
async function ok(method:any,url:string,payload?:any,who='receiver'){const response=await req(method,url,payload,who);assert.equal(response.status,200,JSON.stringify(response.data));return response.data;}
async function policy(extra:any={}){const {policy}=await ok('GET','/incoming/policy');return ok('POST','/incoming/policy',{version:policy.version,timezone:'Africa/Nairobi',deadlines:{CRITICAL:{minutes:2,warningMinutes:1},HIGH:{minutes:5,warningMinutes:2},MEDIUM:{minutes:20,warningMinutes:5},LOW:{minutes:60,warningMinutes:10},REVIEW_REQUIRED:{minutes:10,warningMinutes:3}},emergencyProcedure:'TEST ONLY: contact synthetic clinical lead.',protocol:null,...extra});}
async function draft(urgency='Routine'){return (await ok('POST','/referrals',{patientId:patient,requiredService:'Test service',clinicalSummary:'Synthetic clinical referral for testing only.',urgency},'origin')).referral;}
async function submit(urgency='Routine'){const r=await draft(urgency);return (await ok('POST',`/referrals/${r.id}/transition`,{status:'SUBMITTED',destinationId:destination,version:r.version},'origin')).referral;}
async function current(id:string){return (await db.referral.findUniqueOrThrow({where:{id}}));}
before(async()=>{
  app=await buildApp();await app.ready();
  const hospitals=[];for(const name of ['Origin','Destination','Other'])hospitals.push(await db.hospital.create({data:{name:`Queue ${name} ${suffix}`,registrationNumber:`QUEUE-${name}-${suffix}`,location:'Synthetic city',phone:'000',email:`${name}-${suffix}@test.org`,status:'APPROVED',services:{create:{name:'Test service'}}}}));
  [origin,destination,other]=hospitals.map(h=>h.id);
  patient=(await db.patient.create({data:{hospitalId:origin,identifier:suffix,name:'Synthetic Queue Patient',age:30,sex:'Unknown'}})).id;
  for(const [name,hospitalId,role,permissions] of [['origin',origin,'HOSPITAL_ADMIN',[]],['receiver',destination,'HOSPITAL_ADMIN',['REFERRAL_TRIAGE']],['other',other,'HOSPITAL_ADMIN',[]],['worker',destination,'HEALTHCARE_WORKER',[]],['receivingWorker',destination,'HEALTHCARE_WORKER',['REFERRAL_RECEIVE']],['clinician',destination,'HEALTHCARE_WORKER',['REFERRAL_RECEIVE','REFERRAL_TRIAGE']],['system',null,'SYSTEM_ADMIN',[]]] as const){
    const user=await db.user.create({data:{name,email:`${name}-${suffix}@test.org`.toLowerCase(),role,active:true,passwordHash:await hashPassword(password),...(hospitalId?{memberships:{create:{hospitalId,permissions:[...permissions]}}}:{})}});ids[name]=user.id;
    const login=await app.inject({method:'POST',url:'/auth/login',payload:{email:user.email,password}});assert.equal(login.statusCode,200,login.body);tokens[name]=login.json().accessToken;
  }
});
after(async()=>{await app.close();await db.$disconnect();});

test('incoming referral queue end-to-end and safety boundaries',async t=>{
  await t.test('only receiving staff can read queue and only administrators configure policy',async()=>{
    for(const who of ['worker','system'])assert.equal((await req('GET','/incoming',undefined,who)).status,403);
    assert.equal((await req('GET','/incoming',undefined,'receivingWorker')).status,200);
    await policy();
    const {policy:p}=await ok('GET','/incoming/policy');
    const body={version:p.version,timezone:'Africa/Nairobi',deadlines:{},emergencyProcedure:'',protocol:null};
    assert.equal((await req('POST','/incoming/policy',body,'receivingWorker')).status,403);
    assert.equal((await req('POST','/incoming/policy',{...body,timezone:'Invalid/timezone'})).status,400);
    assert.equal((await req('POST','/incoming/policy',{...body,deadlines:{LOW:{minutes:1,warningMinutes:2}}})).status,400);
    assert.equal((await req('POST','/incoming/policy',{...body,version:0})).status,409);
    assert.equal(await db.operationalUpdate.count({where:{hospitalId:destination,category:'QUEUE_POLICY'}}),1);
  });
  await t.test('receipt time is server-generated, separate from creation and immutable; AI disabled',async()=>{
    const d=await draft();assert.equal(d.receivedAt,null);
    assert.equal((await req('POST','/referrals',{patientId:patient,requiredService:'Test service',clinicalSummary:'Synthetic test',urgency:'Routine',receivedAt:new Date().toISOString()},'origin')).status,400);
    const r=(await ok('POST',`/referrals/${d.id}/transition`,{status:'SUBMITTED',destinationId:destination,version:d.version},'origin')).referral;
    assert.ok(r.submittedAt);assert.ok(r.receivedAt);assert.ok(new Date(r.receivedAt)>=new Date(r.submittedAt));assert.ok(new Date(r.receivedAt)>new Date(r.createdAt));
    assert.equal(r.aiPriority,null);assert.equal(r.confirmedPriority,null);assert.equal(r.assessmentStatus,'DISABLED');assert.equal(r.priorityRank,4);
    assert.equal(new Date(r.acknowledgementDueAt).getTime()-new Date(r.receivedAt).getTime(),10*60000);
    await assert.rejects(db.referral.update({where:{id:r.id},data:{receivedAt:new Date(0)}}));
    assert.equal((await current(r.id)).receivedAt!.toISOString(),r.receivedAt);
    const events=(await ok('GET',`/incoming/${r.id}/events`)).events;assert.ok(events.some((e:any)=>e.kind==='ARRIVED'));assert.ok(events.some((e:any)=>e.kind==='PRIORITIZATION_DISABLED'));
    assert.equal((await req('GET',`/incoming/${r.id}/events`,undefined,'other')).status,404);
    assert.equal((await req('GET',`/incoming/${r.id}/events`,undefined,'worker')).status,403);
  });
  await t.test('confirmed priority precedes arrival age, with stable same-priority ordering and filters',async()=>{
    const ordered=[];
    for(const [name,priority,time] of [['one','CRITICAL','10:30'],['two','HIGH','09:15'],['three','HIGH','09:45'],['four','MEDIUM','08:30'],['five','CRITICAL','10:45']] as const){
      const r=await db.referral.create({data:{originId:origin,destinationId:destination,patientId:patient,requiredService:`Queue order ${suffix}`,clinicalSummary:'Synthetic ordering fixture',urgency:'Routine',createdBy:ids.origin,status:'SUBMITTED',receivedAt:new Date(`2026-11-01T${time}:00Z`),assessmentStatus:'DISABLED'}});
      await ok('POST',`/incoming/${r.id}/priority`,{priority,reason:`Synthetic clinician assessment ${name}`,version:0},'clinician');ordered.push(r.id);
    }
    const q=await ok('GET',`/incoming?service=${encodeURIComponent(`Queue order ${suffix}`)}`);
    assert.deepEqual(q.referrals.map((r:any)=>r.id),[ordered[0],ordered[4],ordered[1],ordered[2],ordered[3]]);
    const high=await ok('GET',`/incoming?service=${encodeURIComponent(`Queue order ${suffix}`)}&priority=HIGH`);assert.deepEqual(high.referrals.map((r:any)=>r.id),[ordered[1],ordered[2]]);
    const page=await ok('GET',`/incoming?service=${encodeURIComponent(`Queue order ${suffix}`)}&limit=2&page=2`);assert.equal(page.total,5);assert.deepEqual(page.referrals.map((r:any)=>r.id),[ordered[1],ordered[2]]);
    const range=await ok('GET',`/incoming?service=${encodeURIComponent(`Queue order ${suffix}`)}&arrivedFrom=2026-11-01T09:30:00Z&arrivedTo=2026-11-01T10:40:00Z`);assert.deepEqual(range.referrals.map((r:any)=>r.id),[ordered[0],ordered[2]]);
    assert.equal((await ok('GET',`/incoming?originId=${other}`)).total,0);
  });
  await t.test('priority changes require clinical permission and reason; concurrent updates are audited once',async()=>{
    const r=await submit();const body={priority:'HIGH',reason:'Synthetic clinical assessment.',version:r.version};
    assert.equal((await req('POST',`/incoming/${r.id}/priority`,body,'receivingWorker')).status,403);
    assert.equal((await req('POST',`/incoming/${r.id}/priority`,body,'origin')).status,404);
    assert.equal((await req('POST',`/incoming/${r.id}/priority`,{...body,reason:' '})).status,400);
    const race=await Promise.all([req('POST',`/incoming/${r.id}/priority`,body,'clinician'),req('POST',`/incoming/${r.id}/priority`,{...body,priority:'LOW'},'clinician')]);assert.deepEqual(race.map(v=>v.status).sort(),[200,409]);
    const saved=await current(r.id);await ok('POST',`/incoming/${r.id}/priority`,{priority:'CRITICAL',reason:'Synthetic revised clinical evidence.',version:saved.version},'clinician');
    const events=(await ok('GET',`/incoming/${r.id}/events`)).events.filter((e:any)=>e.kind.startsWith('PRIORITY_'));
    assert.equal(events.length,2);assert.equal(events[0].actorId,ids.clinician);assert.equal(events[0].previousPriority,saved.confirmedPriority);assert.equal(events[0].priority,'CRITICAL');assert.match(events[0].reason,/revised/);
    assert.equal((await current(r.id)).receivedAt!.toISOString(),r.receivedAt);
    assert.equal((await current(r.id)).acknowledgementDueAt!.getTime()-new Date(r.receivedAt).getTime(),2*60000);
  });
  await t.test('deadline boundaries, warning and overdue alerts do not change priority or duplicate',async()=>{
    const r=await submit();await ok('POST',`/incoming/${r.id}/priority`,{priority:'LOW',reason:'Synthetic clinical review.',version:r.version});
    const saved=await current(r.id),warning=saved.acknowledgementWarningAt!,due=saved.acknowledgementDueAt!;
    assert.equal(queueTiming(saved,new Date(warning.getTime()-1)).acknowledgementStatus,'WAITING');assert.equal(queueTiming(saved,warning).acknowledgementStatus,'APPROACHING');assert.equal(queueTiming(saved,due).acknowledgementStatus,'OVERDUE');
    assert.deepEqual(deadlineFields(null,'LOW',saved.queuePolicySnapshot),{acknowledgementDueAt:null,acknowledgementWarningAt:null});
    await Promise.all([monitorAcknowledgements(warning,destination),monitorAcknowledgements(warning,destination)]);
    await Promise.all([monitorAcknowledgements(due,destination),monitorAcknowledgements(due,destination)]);
    assert.equal(await db.referralQueueEvent.count({where:{referralId:r.id,kind:'ACKNOWLEDGEMENT_APPROACHING'}}),1);assert.equal(await db.referralQueueEvent.count({where:{referralId:r.id,kind:'ACKNOWLEDGEMENT_OVERDUE'}}),1);
    assert.equal((await current(r.id)).confirmedPriority,'LOW');assert.equal((await current(r.id)).priorityRank,3);
    assert.ok((await ok('GET','/workspace/notifications',undefined,'receivingWorker')).notifications.some((n:any)=>n.referralId===r.id));
    assert.equal((await ok('GET','/workspace/notifications',undefined,'worker')).notifications.some((n:any)=>n.referralId===r.id),false);
    await policy({deadlines:{LOW:{minutes:120,warningMinutes:5}}});assert.equal((await current(r.id)).acknowledgementDueAt!.getTime(),due.getTime());
  });
  await t.test('acknowledgement is independent, idempotent, stops monitoring and preserves full lifecycle',async()=>{
    const r=await submit();let saved=r;
    assert.equal((await req('POST',`/incoming/${r.id}/acknowledge`,{version:r.version},'other')).status,404);
    saved=(await ok('POST',`/incoming/${r.id}/acknowledge`,{version:r.version},'receivingWorker')).referral;
    assert.equal(saved.status,'SUBMITTED');assert.ok(saved.acknowledgedAt);assert.equal(saved.acknowledgedBy,ids.receivingWorker);
    const repeated=(await ok('POST',`/incoming/${r.id}/acknowledge`,{version:r.version})).referral;assert.equal(repeated.acknowledgedAt,saved.acknowledgedAt);
    await monitorAcknowledgements(new Date(Date.now()+86400000),destination);assert.equal(await db.referralQueueEvent.count({where:{referralId:r.id,kind:'ACKNOWLEDGEMENT_OVERDUE'}}),0);
    for(const status of ['ACCEPTED','IN_PROGRESS','COMPLETED'])saved=(await ok('POST',`/referrals/${r.id}/transition`,{status,version:saved.version})).referral;
    assert.equal(saved.receivedAt,r.receivedAt);assert.equal(saved.acknowledgedAt,repeated.acknowledgedAt);
    await ok('POST',`/referrals/${r.id}/outcome`,{summary:'Synthetic completed outcome.',actualDelayMinutes:1});await ok('POST',`/referrals/${r.id}/outcome/verify`);
    assert.equal((await ok('GET','/incoming')).referrals.some((x:any)=>x.id===r.id),false);
    assert.ok((await ok('GET','/incoming?status=COMPLETED')).referrals.some((x:any)=>x.id===r.id));
    const rejected=await submit();const decision=(await ok('POST',`/referrals/${rejected.id}/transition`,{status:'REJECTED',reason:'Synthetic reason',version:rejected.version})).referral;assert.ok(decision.acknowledgedAt);
    const cancelled=await submit();await ok('POST',`/referrals/${cancelled.id}/transition`,{status:'CANCELLED',reason:'Synthetic cancellation',version:cancelled.version},'origin');assert.equal((await current(cancelled.id)).receivedAt!.toISOString(),cancelled.receivedAt);
  });
  await t.test('unknown legacy arrivals remain unknown and are never converted to LOW',async()=>{
    const legacy=await db.referral.create({data:{originId:origin,destinationId:destination,patientId:patient,requiredService:'Legacy synthetic',clinicalSummary:'Unknown historical arrival fixture',urgency:'Routine',createdBy:ids.origin,status:'SUBMITTED'}});
    const row=(await ok('GET','/incoming?service=Legacy')).referrals.find((r:any)=>r.id===legacy.id);assert.equal(row.receivedAt,null);assert.equal(row.waitingSeconds,null);assert.equal(row.effectivePriority,null);assert.equal(row.acknowledgementStatus,'ARRIVAL_UNKNOWN');
  });
  await t.test('future protocol integration is safe on AI failure and suggestions never set confirmed priority',async()=>{
    await policy({protocol:syntheticProtocol});const r=await submit('Emergency');
    const url=config.AI_SERVICE_URL;try{config.AI_SERVICE_URL='http://127.0.0.1:1';await assessReferral(r.id);}finally{config.AI_SERVICE_URL=url;}
    let saved=await current(r.id);assert.equal(saved.status,'SUBMITTED');assert.equal(saved.assessmentStatus,'UNAVAILABLE');assert.equal(saved.confirmedPriority,null);assert.equal(saved.aiPriority,null);assert.equal(saved.priorityRank,4);
    saved=(await ok('POST',`/incoming/${r.id}/recommendation`,{version:saved.version})).referral;
    assert.equal(saved.aiPriority,'CRITICAL');assert.equal(saved.confirmedPriority,null);assert.equal(saved.priorityRank,4,'Protocol suggestions do not order the clinical queue.');
    saved=(await ok('POST',`/incoming/${r.id}/priority`,{priority:'HIGH',reason:'Synthetic clinician override with new information.',version:saved.version})).referral;
    saved=(await ok('POST',`/incoming/${r.id}/recommendation`,{version:saved.version})).referral;assert.equal(saved.confirmedPriority,'HIGH');assert.equal(saved.priorityRank,1);
    await policy({protocol:null});assert.equal((await db.queuePolicy.findUniqueOrThrow({where:{hospitalId:destination}})).protocol,null);
  });
});
