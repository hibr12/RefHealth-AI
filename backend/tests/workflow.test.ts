import {test,before,after} from 'node:test';
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {buildApp,db} from '../src/app.js';
import {hashPassword} from '../src/security.js';
import {config,trustedOrigins} from '../src/config.js';
// Test against an isolated PostgreSQL database, never against production.
if(!process.env.DATABASE_URL?.includes('coecare_test'))throw new Error('Use an isolated coecare_test database.');
const suffix=randomUUID().slice(0,8),password='Test-password-strong-123!';
let app:Awaited<ReturnType<typeof buildApp>>,system:string,a:string,b:string,c:string,worker:string;
let ah:string,bh:string,ch:string,referralId:string,patientId:string,adminId:string;
async function req(method:any,url:string,payload?:any,token?:string){const r=await app.inject({method,url,payload,headers:{origin:config.CORS_ADDITIONAL_ORIGINS[0]??config.CORS_ORIGIN,...(token?{authorization:`Bearer ${token}`}:{})}});return {status:r.statusCode,data:r.json(),headers:r.headers};}
async function sign(email:string){const r=await req('POST','/auth/login',{email,password});assert.equal(r.status,200,JSON.stringify(r.data));return r;}
before(async()=>{app=await buildApp();await app.ready();await db.user.create({data:{email:`sys-${suffix}@test.org`,name:'Test platform administrator',role:'SYSTEM_ADMIN',active:true,passwordHash:await hashPassword(password)}});system=(await sign(`sys-${suffix}@test.org`)).data.accessToken;});
after(async()=>{await app.close();await db.$disconnect();});
test('complete database-backed multi-hospital workflow',async t=>{
  await t.test('authentication and origin protection',async()=>{
    assert.equal((await req('GET','/workspace')).status,401);
    assert.equal((await req('POST','/auth/login',{email:'nobody@test.org',password})).status,401);
    for(const origin of trustedOrigins){
      const login=await app.inject({method:'POST',url:'/auth/login',headers:{origin},payload:{email:`sys-${suffix}@test.org`,password}});
      assert.equal(login.statusCode,200,login.body);
      assert.equal(login.json().user.role,'SYSTEM_ADMIN');
      assert.equal(login.headers['access-control-allow-origin'],origin);
      assert.equal(login.headers['access-control-allow-credentials'],'true');
      const cookie=String(login.headers['set-cookie']).split(';')[0];
      const refreshed=await app.inject({method:'POST',url:'/auth/refresh',headers:{origin,cookie}});
      assert.equal(refreshed.statusCode,200,refreshed.body);
      assert.equal(refreshed.headers['access-control-allow-origin'],origin);
      assert.equal((await req('POST','/auth/logout',{},refreshed.json().accessToken)).status,200);
      const wrong=await app.inject({method:'POST',url:'/auth/login',headers:{origin},payload:{email:`sys-${suffix}@test.org`,password:'Incorrect-test-password-123!'}});
      assert.equal(wrong.statusCode,401);
    }
    const sessionCount=await db.session.count();
    for(const origin of ['https://untrusted.example','null','http://127.0.0.1:59999','http://127.0.0.1:5174.evil.example',trustedOrigins[0]+'/path']){
      for(const url of ['/auth/login','/auth/refresh']){
        const csrf=await app.inject({method:'POST',url,headers:{origin},payload:url==='/auth/login'?{email:`sys-${suffix}@test.org`,password}:undefined});
        assert.equal(csrf.statusCode,403,`${origin}: ${csrf.body}`);
        assert.equal(csrf.json().error.message,'Untrusted request origin.');
        assert.equal(csrf.headers['access-control-allow-origin'],undefined);
      }
    }
    assert.equal(await db.session.count(),sessionCount,'Rejected origins must not create a login session.');
  });
  await t.test('registration, approval, and role boundaries',async()=>{
    const ids=[];for(const name of ['A','B','C']){
      const r=await req('POST','/hospitals/register',{name:`Hospital ${name}`,registrationNumber:`REG-${name}-${suffix}`,location:'Test city',phone:'+251000000',email:`hospital-${name}-${suffix}@test.org`,adminName:`Admin ${name}`,adminEmail:`admin-${name}-${suffix}@test.org`,password});assert.equal(r.status,200,JSON.stringify(r.data));ids.push(r.data.hospital.id);
      assert.equal((await req('POST','/auth/login',{email:`admin-${name}-${suffix}@test.org`,password})).status,403);
      assert.equal((await req('PATCH',`/admin/hospitals/${r.data.hospital.id}`,{status:'APPROVED'},system)).status,200);
    }[ah,bh,ch]=ids;a=(await sign(`admin-A-${suffix}@test.org`)).data.accessToken;b=(await sign(`admin-B-${suffix}@test.org`)).data.accessToken;c=(await sign(`admin-C-${suffix}@test.org`)).data.accessToken;
    assert.equal((await req('GET','/workspace',undefined,system)).status,403);
    assert.equal((await req('GET','/admin/users',undefined,a)).status,403);
  });
  await t.test('profile and operational updates persist with isolation',async()=>{
    for(const tok of [a,b,c])assert.equal((await req('POST','/workspace/catalog',{departments:['Medicine'],specialties:['Cardiology'],services:[{name:'Cardiology',available:true}],equipment:[{name:'ECG',available:true}]},tok)).status,200);
    assert.equal((await req('POST','/workspace/capacity',{totalBeds:20,availableBeds:8,staffOnDuty:4,workload:'Low',shared:false},b)).status,200);
    const directory=await req('GET','/hospitals',undefined,a);assert.equal(directory.data.hospitals.find((h:any)=>h.id===bh).capacity,null);
    assert.equal((await req('POST','/workspace/capacity',{totalBeds:2,availableBeds:8,staffOnDuty:4,workload:'Low',shared:true},a)).status,400);
    await req('POST','/workspace/capacity',{totalBeds:20,availableBeds:8,staffOnDuty:4,workload:'Low',shared:true},b);
    const member=await req('POST','/workspace/users',{name:'Worker',email:`worker-${suffix}@test.org`,password,role:'HEALTHCARE_WORKER',permissions:[]},a);assert.equal(member.status,200);worker=(await sign(`worker-${suffix}@test.org`)).data.accessToken;
    assert.equal((await req('POST','/workspace/capacity',{totalBeds:20,availableBeds:8,staffOnDuty:4,workload:'Low',shared:true},worker)).status,403);
  });
  await t.test('patient and draft visibility never cross hospitals',async()=>{
    const p=await req('POST','/patients',{identifier:`patient-${suffix}`,name:'Synthetic Test Patient',age:35,sex:'Female'},worker);assert.equal(p.status,200);patientId=p.data.patient.id;
    const body={patientId,requiredService:'Cardiology',requiredSpecialty:'Cardiology',clinicalSummary:'Synthetic test referral, no real patient.',urgency:'Routine'};
    assert.equal((await req('POST','/referrals',body,c)).status,404);
    const r=await req('POST','/referrals',body,worker);assert.equal(r.status,200);referralId=r.data.referral.id;
    assert.equal((await req('GET',`/referrals/${referralId}`,undefined,b)).status,404);
    assert.equal((await req('GET','/patients',undefined,b)).data.patients.some((x:any)=>x.id===patientId),false);
  });
  await t.test('AI integration records transparent rankings, with no fabricated model results',async()=>{
    const response=await req('POST',`/referrals/${referralId}/intelligence`,undefined,a);assert.equal(response.status,200,JSON.stringify(response.data));
    const p=response.data.prediction;assert.equal(p.component,'recommendation');assert.ok(p.result.ranked_hospitals.some((h:any)=>h.hospital_id===bh));assert.equal(p.result.ranked_hospitals[0].delay_prediction,null);
    const forecast=await req('POST','/workspace/workload',{asOfDate:new Date(Date.now()-86400000).toISOString().slice(0,10)},a);assert.equal(forecast.status,503);assert.match(forecast.data.error.message,/At least seven verified daily records/);
    assert.equal((await req('POST',`/predictions/${p.id}/feedback`,{rating:4,comment:'Useful operational comparison.'},c)).status,404);
    assert.equal((await req('POST',`/predictions/${p.id}/feedback`,{rating:4,comment:'Useful operational comparison.'},worker)).status,200);
    assert.equal((await req('POST',`/predictions/${p.id}/feedback`,{rating:4,comment:'Duplicate feedback.'},worker)).status,409);
    const url=config.AI_SERVICE_URL;
    try{config.AI_SERVICE_URL='http://127.0.0.1:1';assert.equal((await req('POST',`/referrals/${referralId}/intelligence`,undefined,a)).status,503);assert.equal((await req('GET',`/referrals/${referralId}`,undefined,a)).data.referral.status,'DRAFT');}finally{config.AI_SERVICE_URL=url;}
  });
  await t.test('referral lifecycle, cross-hospital permissions, and concurrent writes',async()=>{
    const path=`/referrals/${referralId}/transition`;
    assert.equal((await req('POST',path,{status:'SUBMITTED',destinationId:ah,version:0},a)).status,400);
    assert.equal((await req('POST',path,{status:'SUBMITTED',destinationId:bh,version:0},worker)).status,200);
    assert.equal((await req('GET',`/referrals/${referralId}`,undefined,b)).status,200);
    assert.equal((await req('GET',`/referrals/${referralId}`,undefined,c)).status,404);
    assert.equal((await req('POST',path,{status:'ACCEPTED',version:1},a)).status,403);
    assert.equal((await req('POST',path,{status:'REJECTED',version:1},b)).status,400);
    const concurrent=await Promise.all([req('POST',path,{status:'ACCEPTED',version:1},b),req('POST',path,{status:'ACCEPTED',version:1},b)]);assert.deepEqual(concurrent.map(x=>x.status).sort(),[200,409]);
    assert.equal((await req('POST',path,{status:'COMPLETED',version:2},b)).status,409);
    assert.equal((await req('POST',path,{status:'IN_PROGRESS',version:2},b)).status,200);
    assert.equal((await req('POST',path,{status:'COMPLETED',version:3},b)).status,200);
    assert.equal((await req('POST',`/referrals/${referralId}/outcome`,{summary:'Synthetic completed referral outcome',actualDelayMinutes:35},b)).status,200);
    assert.equal((await req('POST',`/referrals/${referralId}/outcome/verify`,undefined,a)).status,404);
    assert.equal((await req('POST',`/referrals/${referralId}/outcome/verify`,undefined,b)).status,200);
    assert.equal((await req('GET',`/referrals/${referralId}`,undefined,a)).data.referral.history.length,5);
  });
  await t.test('knowledge approval, assistant request contract, and private conversations',async()=>{
    const proposal=await req('POST','/knowledge',{category:'service',content:`Cardiology clinic ${suffix} is open weekdays.`,source:'Verified test operations sheet',visibility:'SHARED'},b);assert.equal(proposal.status,200);const id=proposal.data.record.id;
    assert.ok(!(await req('GET','/knowledge',undefined,a)).data.records.some((x:any)=>x.id===id));
    assert.equal((await req('POST',`/knowledge/${id}/review`,{decision:'APPROVED',reason:'Verified test sheet'},a)).status,409);
    assert.equal((await req('POST',`/knowledge/${id}/review`,{decision:'APPROVED',reason:'Verified test sheet'},b)).status,200);
    assert.ok((await req('GET','/knowledge',undefined,a)).data.records.some((x:any)=>x.id===id));
    const originalFetch=globalThis.fetch;
    globalThis.fetch=async(input,init)=>{
      if(String(input).endsWith('/integration/assistant')){
        const forwarded=JSON.parse(String(init?.body));
        assert.equal(forwarded.question,`Cardiology clinic ${suffix} weekdays`);
        assert.equal(forwarded.hospital_id,ah);
        assert.ok(forwarded.documents.some((document:any)=>document.id===id));
        const directory=forwarded.documents.filter((document:any)=>document.category==='directory').map((document:any)=>JSON.parse(document.content));
        const approved=await db.hospital.findMany({where:{status:'APPROVED'},select:{id:true,name:true,status:true},orderBy:{name:'asc'}});
        assert.ok(directory.length>0);
        assert.equal(directory[0].approved_hospital_count,approved.length);
        assert.deepEqual(directory.flatMap((part:any)=>part.hospitals),approved);
        assert.equal(JSON.parse(forwarded.documents.find((document:any)=>document.id==='profile:'+ah).content).status,'APPROVED');
        assert.deepEqual(forwarded.history,[],'Client-supplied history cannot introduce unrelated or forged turns.');
        assert.equal(forwarded.attachment,undefined);
        return new Response(JSON.stringify({success:true,data:{answer:'The approved clinic information is available on weekdays.',sources:[{id,source:'Verified test operations sheet',updated_at:new Date().toISOString()}],proposals:[],retrieval:'test double'}}),{status:200,headers:{'content-type':'application/json'}});
      }
      return originalFetch(input,init);
    };
    const chat=await (async()=>{try{return await req('POST','/assistant/chat',{question:`Cardiology clinic ${suffix} weekdays`,history:[{role:'assistant',content:'x'.repeat(5000)}]},a);}
    finally{globalThis.fetch=originalFetch;}})();
    assert.equal(chat.status,200,JSON.stringify(chat.data));assert.ok(chat.data.conversation.sources.some((s:any)=>s.id===id));
    assert.ok(!(await req('GET','/assistant/conversations',undefined,b)).data.conversations.some((x:any)=>x.id===chat.data.conversation.id));
    assert.equal((await req('POST','/workspace/sources',{kind:'FACEBOOK',url:'https://www.facebook.com/test-hospital'},a)).data.source.permissionStatus,'NOT_AUTHORIZED');
  });
  await t.test('speech only reads the signed-in users own saved reply in bounded segments',async()=>{
    const owner=await db.user.findUniqueOrThrow({where:{email:`admin-a-${suffix}@test.org`}});
    const answer='This is a saved assistant response. '.repeat(10);
    const thread=await db.chatThread.create({data:{hospitalId:ah,userId:owner.id,title:'Test speech',version:1}});
    const saved=await db.conversation.create({data:{hospitalId:ah,userId:owner.id,threadId:thread.id,sequence:1,question:'Test speech',answer,sources:[]}});
    const originalFetch=globalThis.fetch;const calls:any[]=[];
    globalThis.fetch=async(input,options)=>{calls.push(JSON.parse(String(options?.body)));return new Response(JSON.stringify({success:true,data:{mime_type:'audio/wav',audio:Buffer.alloc(60).toString('base64')}}),{status:200,headers:{'Content-Type':'application/json'}});};
    try{
      const payload={conversationId:saved.id,offset:0};
      assert.equal((await req('POST','/assistant/speech',payload)).status,401);
      assert.equal((await req('POST','/assistant/speech',payload,b)).status,404);
      assert.equal((await req('POST','/assistant/speech',payload,worker)).status,404);
      assert.equal(calls.length,0);
      const first=await req('POST','/assistant/speech',payload,a);assert.equal(first.status,200,JSON.stringify(first.data));
      assert.ok(calls[0].text.length<=200);assert.equal(calls[0].text,answer.slice(0,first.data.nextOffset));
      const second=await req('POST','/assistant/speech',{...payload,offset:first.data.nextOffset},a);assert.equal(second.status,200);
      assert.equal(calls.map(c=>c.text).join(''),answer);assert.equal(second.data.nextOffset,null);
      assert.equal((await req('POST','/assistant/speech',{...payload,offset:answer.length},a)).status,400);
    }finally{globalThis.fetch=originalFetch;}
  });
  await t.test('voice transcripts persist privately without storing audio bytes',async()=>{
    const originalFetch=globalThis.fetch,audio=Buffer.from('Synthetic audio for request contract testing').toString('base64');
    let includeTranscript=true;
    globalThis.fetch=async(input,init)=>{
      if(String(input).endsWith('/integration/assistant')){
        const forwarded=JSON.parse(String(init?.body));
        assert.equal(forwarded.attachment.mime_type,'audio/mp4');
        assert.equal(forwarded.attachment.data,audio);
        return new Response(JSON.stringify({success:true,data:{answer:'I help with coordination.',sources:[],proposals:[],...(includeTranscript?{transcript:'What is your purpose?',user_message:'What is your purpose?'}:{})}}),{status:200,headers:{'content-type':'application/json'}});
      }return originalFetch(input,init);
    };
    try{
      const payload={question:'Please answer my voice message.',attachment:{mime_type:'audio/mp4',data:audio}};
      const chat=await req('POST','/assistant/chat',payload,a);
      assert.equal(chat.status,200,JSON.stringify(chat.data));
      assert.equal(chat.data.conversation.question,'What is your purpose?');
      assert.ok(!JSON.stringify(chat.data).includes(audio));
      const saved=await db.conversation.findUniqueOrThrow({where:{id:chat.data.conversation.id}});
      assert.equal(saved.question,'What is your purpose?');assert.ok(!JSON.stringify(saved).includes(audio));
      assert.ok(!(await req('GET','/assistant/conversations',undefined,b)).data.conversations.some((row:any)=>row.id===saved.id));
      includeTranscript=false;const count=await db.conversation.count();
      assert.equal((await req('POST','/assistant/chat',payload,a)).status,502);
      assert.equal(await db.conversation.count(),count);
    }finally{globalThis.fetch=originalFetch;}
  });
  await t.test('assistant has fresh role-scoped workspace facts and excludes private fields',async()=>{
    const privateMarker=`PRIVATE-KNOWLEDGE-${suffix}`,patientMarker=`PRIVATE-PATIENT-${suffix}`,clinicalMarker=`PRIVATE-CLINICAL-${suffix}`;
    await db.knowledgeRecord.create({data:{hospitalId:bh,category:'operational',content:privateMarker,source:'Private fixture',status:'APPROVED',visibility:'PRIVATE',createdBy:'test'}});
    const patient=await db.patient.create({data:{hospitalId:bh,identifier:patientMarker,name:patientMarker,age:30,sex:'Female'}});
    const incoming=await db.referral.create({data:{originId:bh,destinationId:ah,patientId:patient.id,requiredService:'Cardiology',clinicalSummary:clinicalMarker,urgency:'Routine',status:'SUBMITTED',createdBy:'test'}});
    await db.modelVersion.create({data:{id:`workspace-model-${suffix}`,component:'workload',metadata:{source:'synthetic test'}}});
    await db.prediction.create({data:{hospitalId:ah,component:'workload',modelVersionId:`workspace-model-${suffix}`,result:{predicted_workload:'Low',forecast_date:'2026-11-12',private_note:'FORECAST-INTERNAL-SECRET'}}});
    await req('POST','/workspace/capacity',{totalBeds:20,availableBeds:9,staffOnDuty:4,workload:'Low',shared:false},a);
    await req('POST','/workspace/capacity',{totalBeds:20,availableBeds:7,staffOnDuty:4,workload:'Low',shared:false},b);
    const originalFetch=globalThis.fetch;let forwarded:any,badCitation=false;
    globalThis.fetch=async(input,init)=>{
      if(String(input).endsWith('/models'))return new Response(JSON.stringify({success:true,data:[{active:true,component:'delay',version:'test-legacy',metadata:{status:'legacy_experimental',data_source:'synthetic',secret:'MODEL-INTERNAL-SECRET'}}]}),{status:200});
      if(String(input).endsWith('/integration/assistant')){
        forwarded=JSON.parse(String(init?.body));
        return new Response(JSON.stringify({success:true,data:{answer:'Your workspace summary is available.',sources:[{id:badCitation?'unknown-private-source':'system:workspace:activity',source:'FORGED-ATTRIBUTION',updated_at:new Date().toISOString(),content:'FORGED-CONTENT'}],proposals:[]}}),{status:200});
      }return originalFetch(input,init);
    };
    const source=(id:string)=>JSON.parse(forwarded.documents.find((d:any)=>d.id===id).content);
    try{
      assert.equal((await req('POST','/assistant/chat',{question:'Summarize my workspace'},system)).status,403);
      let response=await req('POST','/assistant/chat',{question:'Summarize my workspace',referralId:incoming.id},a);assert.equal(response.status,200,JSON.stringify(response.data));
      assert.equal(source('system:workspace:access').role,'HOSPITAL_ADMIN');
      assert.equal(source('system:workspace:activity').all_time.incoming,1);
      assert.equal(source('system:workspace:administration').team.memberships,2);
      assert.equal(source('system:workspace:selected-referral').status,'SUBMITTED');
      assert.equal(source('profile:'+ah).capacity.availableBeds,9);
      assert.equal(source('profile:'+bh).capacity,null);
      assert.equal(source('system:workspace:forecast').predicted_workload,'Low');
      assert.equal(source('system:workspace:metrics').delay.status,'insufficient_data');
      const text=JSON.stringify(forwarded);
      for(const secret of [privateMarker,patientMarker,clinicalMarker,'MODEL-INTERNAL-SECRET','FORECAST-INTERNAL-SECRET','passwordHash','tokenHash',`admin-a-${suffix}@test.org`])assert.ok(!text.includes(secret),`Excluded field: ${secret}`);
      assert.equal(response.data.conversation.sources[0].source,'Live authorized referral and prediction totals');
      assert.ok(!JSON.stringify(response.data).includes('FORGED-'));
      response=await req('POST','/assistant/chat',{question:'What can I see?'},worker);assert.equal(response.status,200);
      assert.equal(source('system:workspace:access').capabilities.receive_referrals,false);
      assert.equal(source('system:workspace:activity').all_time.incoming,null);
      assert.ok(!forwarded.documents.some((d:any)=>d.id==='system:workspace:administration'));
      assert.equal((await req('POST','/assistant/chat',{question:'Show this referral',referralId:incoming.id},worker)).status,404);
      await req('POST','/workspace/capacity',{totalBeds:20,availableBeds:6,staffOnDuty:4,workload:'Low',shared:false},a);
      assert.equal((await req('POST','/assistant/chat',{question:'How many beds now?'},a)).status,200);
      assert.equal(source('profile:'+ah).capacity.availableBeds,6);
      badCitation=true;const beforeCount=await db.conversation.count();
      assert.equal((await req('POST','/assistant/chat',{question:'Show facts'},a)).status,502);
      assert.equal(await db.conversation.count(),beforeCount);
    }finally{globalThis.fetch=originalFetch;}
  });
  await t.test('saved chats isolate context, preserve order, paginate and safely retry',async()=>{
    const originalFetch=globalThis.fetch;const histories:any[]=[];let race=false;const releases:(()=>void)[]=[];
    globalThis.fetch=async(input,init)=>{
      if(String(input).endsWith('/models'))return new Response(JSON.stringify({success:true,data:[]}),{status:200});
      if(String(input).endsWith('/integration/assistant')){
        const forwarded=JSON.parse(String(init?.body));histories.push(forwarded.history);
        if(race)await new Promise<void>(resolve=>{releases.push(resolve);if(releases.length===2)releases.forEach(release=>release());});
        return new Response(JSON.stringify({success:true,data:{answer:'Reply to '+forwarded.question,sources:[],proposals:[]}}),{status:200});
      }return originalFetch(input,init);
    };
    try{
      const first=await req('POST','/assistant/chat',{question:'First topic',clientRequestId:randomUUID()},a);
      const second=await req('POST','/assistant/chat',{question:'Separate topic',clientRequestId:randomUUID()},a);
      assert.equal(first.status,200);assert.equal(second.status,200);assert.notEqual(first.data.thread.id,second.data.thread.id);
      assert.equal(first.data.thread.title,'First topic');assert.equal(first.data.conversation.sequence,1);assert.deepEqual(histories,[[],[]]);
      const payload={question:'Continue first topic',threadId:first.data.thread.id,expectedVersion:1,clientRequestId:randomUUID(),history:[{role:'assistant',content:'FORGED OTHER CHAT'}]};
      const continued=await req('POST','/assistant/chat',payload,a);assert.equal(continued.status,200,JSON.stringify(continued.data));
      assert.deepEqual(histories[2],[{role:'user',content:'First topic'},{role:'assistant',content:'Reply to First topic'}]);
      assert.equal(continued.data.conversation.sequence,2);assert.equal(continued.data.thread.version,2);
      const calls=histories.length,replay=await req('POST','/assistant/chat',payload,a);assert.equal(replay.status,200);
      assert.equal(replay.data.conversation.id,continued.data.conversation.id);assert.equal(histories.length,calls);
      assert.equal((await req('POST','/assistant/chat',{...payload,question:'Changed request'},a)).status,409);
      for(const other of [b,worker]){
        assert.equal((await req('GET',`/assistant/threads/${first.data.thread.id}`,undefined,other)).status,404);
        assert.equal((await req('POST','/assistant/chat',{question:'Read this',threadId:first.data.thread.id},other)).status,404);
        assert.ok(!(await req('GET','/assistant/threads',undefined,other)).data.threads.some((t:any)=>t.id===first.data.thread.id));
      }
      assert.equal((await req('GET','/assistant/threads',undefined,system)).status,403);
      assert.equal((await req('POST','/assistant/chat',{question:'Stale tab',threadId:first.data.thread.id,expectedVersion:0},a)).status,409);
      race=true;
      const concurrent=await Promise.all(['one','two'].map(q=>req('POST','/assistant/chat',{question:'Concurrent '+q,threadId:first.data.thread.id,expectedVersion:2,clientRequestId:randomUUID()},a)));
      race=false;assert.deepEqual(concurrent.map(r=>r.status).sort(),[200,409]);
      const page1=await req('GET','/assistant/threads?limit=1',undefined,a);assert.equal(page1.data.threads[0].id,first.data.thread.id);assert.ok(page1.data.nextCursor);
      const page2=await req('GET','/assistant/threads?limit=1&cursor='+encodeURIComponent(page1.data.nextCursor),undefined,a);assert.notEqual(page2.data.threads[0].id,first.data.thread.id);
      const recent=await req('GET',`/assistant/threads/${first.data.thread.id}?limit=1`,undefined,a);assert.equal(recent.data.conversations[0].sequence,3);
      const older=await req('GET',`/assistant/threads/${first.data.thread.id}?before=${recent.data.nextBefore}&limit=100`,undefined,a);assert.deepEqual(older.data.conversations.map((c:any)=>c.sequence),[1,2]);
      assert.equal(older.data.nextBefore,null);
      const owner=await db.user.findUniqueOrThrow({where:{email:`admin-a-${suffix}@test.org`}});
      await db.conversation.createMany({data:Array.from({length:45},(_,i)=>({hospitalId:ah,userId:owner.id,threadId:second.data.thread.id,sequence:i+2,question:'Historical question '+(i+2),answer:'Historical reply',sources:[]}))});
      await db.chatThread.update({where:{id:second.data.thread.id},data:{version:46}});
      const latest=await req('GET',`/assistant/threads/${second.data.thread.id}`,undefined,a);assert.equal(latest.data.conversations.length,40);assert.equal(latest.data.conversations[0].sequence,7);
      const earliest=await req('GET',`/assistant/threads/${second.data.thread.id}?before=${latest.data.nextBefore}`,undefined,a);assert.deepEqual(earliest.data.conversations.map((c:any)=>c.sequence),[1,2,3,4,5,6]);
      assert.ok(!JSON.stringify(latest.data).includes('requestDigest'));
    }finally{globalThis.fetch=originalFetch;}
  });
  await t.test('refresh rotation, logout, and suspension revoke access',async()=>{
    const login=await sign(`admin-A-${suffix}@test.org`);const cookie=String(login.headers['set-cookie']).split(';')[0];
    const refreshed=await app.inject({method:'POST',url:'/auth/refresh',headers:{cookie}});assert.equal(refreshed.statusCode,200);
    assert.equal((await app.inject({method:'POST',url:'/auth/refresh',headers:{cookie}})).statusCode,401);
    const access=refreshed.json().accessToken;assert.equal((await req('POST','/auth/logout',undefined,access)).status,200);assert.equal((await req('GET','/workspace',undefined,access)).status,401);
    await req('PATCH',`/admin/hospitals/${ah}`,{status:'SUSPENDED'},system);assert.equal((await req('GET','/workspace',undefined,a)).status,403);
  });
  await t.test('recovery token is single-use and learning export is service-only',async()=>{
    const user=await db.user.findUniqueOrThrow({where:{email:`admin-c-${suffix}@test.org`}});
    const issued=await req('POST',`/admin/users/${user.id}/token`,{purpose:'RESET'},system);assert.equal(issued.status,200);
    assert.equal((await req('POST','/auth/complete',{token:issued.data.token,password:'Replacement-test-password-123!'})).status,200);
    assert.equal((await req('POST','/auth/complete',{token:issued.data.token,password})).status,400);
    assert.equal((await req('GET','/workspace',undefined,c)).status,401);
    assert.equal((await req('GET','/internal/learning-export?kind=daily',undefined,b)).status,401);
    const exported=await app.inject({method:'GET',url:'/internal/learning-export?kind=daily',headers:{'x-api-key':config.AI_SERVICE_KEY}});assert.equal(exported.statusCode,200);
  });
});
