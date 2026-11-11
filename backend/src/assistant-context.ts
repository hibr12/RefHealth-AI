import type {Prisma} from '../generated/prisma/index.js';
import {db,type Actor} from './app.js';
import {referralScope} from './referrals.js';
import {fail} from './security.js';
import {assistantDirectory} from './assistant-directory.js';
import {ai} from './gateway.js';
import {intelligenceMetrics} from './metrics.js';

export type AssistantSource={id:string;hospital_id:string;category:string;source:string;content:string;updated_at:string;review_at:string|null};
const statuses=['DRAFT','SUBMITTED','ACCEPTED','REJECTED','IN_PROGRESS','COMPLETED','CANCELLED'];
const counts=(rows:{status:string;_count:number}[])=>Object.fromEntries(statuses.map(status=>[status,rows.find(row=>row.status===status)?._count??0]));

/** Context is constructed from server-authorized queries, never client role claims. */
export async function assistantContext(actor:Actor,referralId?:string):Promise<AssistantSource[]>{
  if(!actor.hospitalId) return fail(403,'Hospital workspace required.');
  const hospitalId=actor.hospitalId,admin=actor.role==='HOSPITAL_ADMIN';
  const canReceive=admin||actor.permissions.includes('REFERRAL_RECEIVE');
  const now=new Date(),asOf=now.toISOString();
  // Referral submission uses UTC+03:00 throughout this application.
  const local=new Date(now.getTime()+3*3600000);
  const today=new Date(Date.UTC(local.getUTCFullYear(),local.getUTCMonth(),local.getUTCDate())-3*3600000);
  const endToday=new Date(today.getTime()+86400000);
  const doc=(id:string,category:string,source:string,data:unknown):AssistantSource=>({id,hospital_id:hospitalId,category,source,content:JSON.stringify(data),updated_at:asOf,review_at:null});
  const documents=await db.$transaction(async tx=>{
    const scope=referralScope(actor),visibleKnowledge:Prisma.KnowledgeRecordWhereInput={status:'APPROVED',hospital:{status:'APPROVED'},OR:[{hospitalId},{visibility:{in:['PUBLIC','SHARED']}}]};
    const hospitals=await tx.hospital.findMany({where:{status:'APPROVED'},orderBy:{name:'asc'},select:{id:true,name:true,status:true,location:true,operatingHours:true,updatedAt:true,
      departments:{select:{name:true}},specialties:{select:{name:true}},services:{select:{name:true,available:true,updatedAt:true}},equipment:{select:{name:true,available:true,updatedAt:true}},
      capacity:{select:{totalBeds:true,availableBeds:true,staffOnDuty:true,workload:true,shared:true,updatedAt:true}}}});
    const ownHospital=hospitals.find(h=>h.id===hospitalId);
    const [records,knowledgeTotal,referrals,outgoing,incoming,predictions,daily,latestDaily]=await Promise.all([
      tx.knowledgeRecord.findMany({where:visibleKnowledge,orderBy:{updatedAt:'desc'},take:300,select:{id:true,hospitalId:true,content:true,category:true,source:true,updatedAt:true,reviewAt:true}}),
      tx.knowledgeRecord.count({where:visibleKnowledge}),
      tx.referral.groupBy({by:['status'],where:scope,_count:true}),
      tx.referral.count({where:{originId:hospitalId}}),
      canReceive?tx.referral.count({where:{AND:[scope,{destinationId:hospitalId}]}}):Promise.resolve(null),
      tx.prediction.groupBy({by:['component'],where:{hospitalId},_count:true}),
      tx.operationalUpdate.count({where:{hospitalId,category:'DAILY_VERIFIED'}}),
      tx.operationalUpdate.findFirst({where:{hospitalId,category:'DAILY_VERIFIED'},orderBy:{createdAt:'desc'},select:{createdAt:true}}),
    ]);
    const documents:AssistantSource[]=records.map(k=>({id:k.id,hospital_id:k.hospitalId,content:k.content,category:k.category,source:k.source,updated_at:k.updatedAt.toISOString(),review_at:k.reviewAt?.toISOString()??null}));
    documents.push(...assistantDirectory(hospitals,hospitalId));
    for(const h of hospitals){
      const capacity=h.capacity&&(h.id===hospitalId||h.capacity.shared)?{...h.capacity,age_minutes:Math.max(0,Math.floor((now.getTime()-h.capacity.updatedAt.getTime())/60000)),fresh:now>=h.capacity.updatedAt&&now.getTime()-h.capacity.updatedAt.getTime()<=7200000}:null;
      const data={name:h.name,status:h.status,location:h.location,operatingHours:h.operatingHours||null,departments:h.departments,specialties:h.specialties,services:h.services,equipment:h.equipment,capacity,
        capacity_note:capacity?'Observed capacity; availability must be confirmed before transfer.':'Capacity is unshared or not recorded; this does not mean zero beds.'};
      const updated=Math.max(h.updatedAt.getTime(),...h.services.map(s=>s.updatedAt.getTime()),...h.equipment.map(e=>e.updatedAt.getTime()),capacity?new Date(capacity.updatedAt).getTime():0);
      const source={...doc('profile:'+h.id,'profile','Hospital-maintained profile',data),hospital_id:h.id,updated_at:new Date(updated).toISOString()};
      if(source.content.length<=28000)documents.push(source);
      else{
        // Preserve the full catalog without exceeding the AI document contract.
        const {departments,specialties,services,equipment,...basic}=data;
        documents.push({...source,content:JSON.stringify({...basic,catalog_in_separate_parts:true})});
        const entries=[...departments.map(x=>({kind:'department',...x})),...specialties.map(x=>({kind:'specialty',...x})),...services.map(x=>({kind:'service',...x})),...equipment.map(x=>({kind:'equipment',...x}))];
        for(let i=0;i<entries.length;i+=40)documents.push({...source,id:`profile:${h.id}:catalog:${i/40+1}`,content:JSON.stringify({name:h.name,status:h.status,catalog:entries.slice(i,i+40)})});
      }
    }
    documents.push(doc('system:workspace:access','workspace','Current workspace permissions',{
      hospital_name:ownHospital?.name,role:actor.role,permissions:actor.permissions,scope:'This signed-in hospital workspace only; no platform-wide private records.',
      capabilities:{manage_hospital_profile:admin,manage_team:admin,manage_external_sources:admin,review_knowledge:admin||actor.permissions.includes('KNOWLEDGE_REVIEW'),create_and_send_referrals:true,receive_referrals:canReceive,assign_clinical_priority:canReceive&&actor.permissions.includes('REFERRAL_TRIAGE'),configure_queue_policy:admin,view_own_hospital_predictions:true,system_administration:false},
      privacy:'No patient identities, clinical summaries, account credentials, session tokens, staff identities or other users conversations are supplied. Private data from other hospitals is excluded.',
      limits:{knowledge_records_available:knowledgeTotal,knowledge_records_supplied:records.length,knowledge_window:'Up to 300 most recently updated authorized approved records; this is not the entire knowledge database.',referral_details:'Select a Referral ID to discuss its authorized patient-free status and prediction context.',actions:'Chat explains; it cannot edit records, approve hospitals, send referrals or train models.'},
    }));
    const [createdToday,updatedToday,verifiedOutcomes]=await Promise.all([
      tx.referral.count({where:{AND:[scope,{createdAt:{gte:today,lt:endToday}}]}}),
      tx.referral.count({where:{AND:[scope,{updatedAt:{gte:today,lt:endToday}}]}}),
      tx.referralOutcome.count({where:{verifiedAt:{not:null},referral:scope}}),
    ]);
    let incomingQueue:Record<string,unknown>|null=null;
    if(canReceive){
      const active={destinationId:hospitalId,status:{in:['SUBMITTED','ACCEPTED','IN_PROGRESS'] as const}};
      const [priorities,overdue,queuePolicy]=await Promise.all([
        tx.referral.groupBy({by:['confirmedPriority'],where:{...active,status:{in:[...active.status.in]}},_count:true}),
        tx.referral.count({where:{destinationId:hospitalId,status:'SUBMITTED',acknowledgedAt:null,acknowledgementDueAt:{lte:new Date(asOf)}}}),
        tx.queuePolicy.findUnique({where:{hospitalId},select:{timezone:true,protocol:true}}),
      ]);
      incomingQueue={active_by_confirmed_priority:priorities.map(p=>({priority:p.confirmedPriority??'CLINICAL_REVIEW_REQUIRED',count:p._count})),acknowledgement_overdue:overdue,timezone:queuePolicy?.timezone??'Africa/Nairobi',automatic_recommendations:queuePolicy?.protocol?'Approved protocol configured; clinician confirmation is still required.':'Disabled: no approved, clinically validated protocol supplied.',ordering:'Clinician-confirmed Critical, High, Medium, Low; earliest recorded receipt first within each priority. Unassigned referrals are flagged for clinical review. Unknown historical arrival times are never guessed.'};
    }
    documents.push(doc('system:workspace:activity','workspace','Live authorized referral and prediction totals',{
      as_of:asOf,hospital_name:ownHospital?.name,scope:canReceive?'Outgoing referrals plus non-draft incoming referrals.':'Outgoing referrals only; incoming referrals require receiving permission.',
      all_time:{referrals_by_status:counts(referrals),visible_referrals:referrals.reduce((n,r)=>n+r._count,0),outgoing,incoming,verified_outcomes:verifiedOutcomes,predictions_by_component:predictions.map(p=>({component:p.component,count:p._count}))},
      today:{timezone:'UTC+03:00',from:today.toISOString(),until:endToday.toISOString(),created:createdToday,updated:updatedToday},
      incoming_queue:incomingQueue,
      definitions:{pending:'SUBMITTED means awaiting a receiving decision; DRAFT is not sent.',updated_today:'Distinct visible records last updated today, not an audit-event count.',incoming:canReceive?'Non-draft incoming referrals visible to this role.':'Not authorized; null is not zero.'},
      workload_data:{verified_daily_record_count:daily,latest_record_saved_at:latestDaily?.createdAt.toISOString()??null,requirement:'Forecasting needs seven consecutive verified completed-day records and an approved real-data model; a total count alone does not establish readiness.'},
    }));
    const forecast=await tx.prediction.findFirst({where:{hospitalId,component:'workload'},orderBy:{createdAt:'desc'},select:{modelVersionId:true,createdAt:true,result:true}});
    const result=forecast?.result as Record<string,unknown>|undefined;
    documents.push(doc('system:workspace:forecast','workspace','Latest saved hospital workload forecast',{
      as_of:asOf,available:!!forecast,model_version:forecast?.modelVersionId??null,saved_at:forecast?.createdAt.toISOString()??null,
      predicted_workload:typeof result?.predicted_workload==='string'?result.predicted_workload:null,forecast_date:typeof result?.forecast_date==='string'?result.forecast_date:null,
      limitations:'A saved prediction is not a current observation or verified outcome. Confirm its forecast date; chat does not run a new forecast.',
    }));
    if(admin){
      const [members,knowledge,sourceStatus,jobs,events]=await Promise.all([
        tx.membership.findMany({where:{hospitalId},select:{active:true,user:{select:{role:true,active:true}}}}),
        tx.knowledgeRecord.groupBy({by:['status'],where:{hospitalId},_count:true}),
        tx.externalSource.groupBy({by:['kind','status','permissionStatus'],where:{hospitalId},_count:true}),
        tx.sourceJob.groupBy({by:['status'],where:{hospitalId},_count:true}),
        tx.auditLog.findMany({where:{hospitalId},orderBy:{createdAt:'desc'},take:20,select:{action:true,createdAt:true}}),
      ]);
      documents.push(doc('system:workspace:administration','workspace','Live hospital administration summary',{
        as_of:asOf,scope:'Own hospital; administrator access only.',
        team:{memberships:members.length,active:members.filter(m=>m.active&&m.user.active).length,inactive:members.filter(m=>!m.active||!m.user.active).length,
          by_role:['HOSPITAL_ADMIN','HEALTHCARE_WORKER'].map(role=>({role,total:members.filter(m=>m.user.role===role).length,active:members.filter(m=>m.user.role===role&&m.active&&m.user.active).length}))},
        knowledge_by_status:knowledge.map(k=>({status:k.status,count:k._count})),external_sources:sourceStatus.map(s=>({kind:s.kind,status:s.status,permission_status:s.permissionStatus,count:s._count})),source_jobs:jobs.map(j=>({status:j.status,count:j._count})),
        recent_events:{limit:20,complete_history:false,events:events.map(e=>({action:e.action,at:e.createdAt.toISOString()}))},
      }));
    }else if(actor.permissions.includes('KNOWLEDGE_REVIEW')){
      const pending=await tx.knowledgeRecord.count({where:{hospitalId,status:'PENDING'}});
      documents.push(doc('system:workspace:review','workspace','Current authorized review queue',{pending_knowledge_proposals:pending,scope:'Own hospital; proposals are unverified until approved.'}));
    }
    if(referralId){
      const referral=await tx.referral.findFirst({where:{id:referralId,...scope},select:{id:true,status:true,requiredService:true,requiredSpecialty:true,urgency:true,createdAt:true,updatedAt:true,origin:{select:{name:true}},destination:{select:{name:true}},history:{select:{status:true,createdAt:true},orderBy:{createdAt:'asc'}},outcome:{select:{actualDelayMinutes:true,verifiedAt:true}}}});
      if(!referral)return fail(404,'Referral not found.');
      documents.push(doc('system:workspace:selected-referral','workspace','Selected authorized referral status',{...referral,scope:'Selected referral only; patient details and free-text clinical fields are excluded.'}));
      const saved=await tx.prediction.findMany({where:{hospitalId,referralId},orderBy:{createdAt:'desc'},take:3,select:{id:true,result:true,createdAt:true}});
      for(const p of saved)documents.push({...doc(p.id,'prediction','Experimental AI prediction',p.result),updated_at:p.createdAt.toISOString()});
    }
    return documents;
  },{isolationLevel:'RepeatableRead',timeout:15000});
  documents.push(doc('system:workspace:guide','workspace','RefHealth application workflow guide',{
    navigation:{overview:'Referral totals and workload observations',directory:'Hospital network: approved hospitals and shared capacity',referrals:'Create a patient record and draft referral, review eligible hospitals, select a destination and submit; the receiving hospital accepts/rejects, starts care and records completion/outcomes.',incoming_queue:'Incoming queue: record receipt, acknowledge separately from acceptance, review confirmed priority and arrival ordering, monitor configured deadlines and review audit history. REFERRAL_TRIAGE is required for all clinical priority reviewers, including administrators. Automatic recommendations are disabled without an approved, clinically validated protocol.',intelligence:'View saved predictions, request a workload forecast, submit feedback, inspect model and verified-outcome metrics.',knowledge:'Propose operational knowledge; an authorized reviewer must approve it before the assistant uses it as evidence.',administration:'Hospital administrators use Hospital profile, Operations, Team & permissions and External sources.'},
    access:'Hospital administrators manage their hospital. Workers create/send referrals; receiving requires REFERRAL_RECEIVE, reviewing knowledge requires KNOWLEDGE_REVIEW. System administrators approve registrations and manage platform access in a separate workspace.',
    recovery:'Use Forgot password, then contact the platform administrator to verify identity and receive a single-use reset token. Existing passwords cannot be retrieved.',
    integrations:'Permitted public website/feed collection must be authorized by a hospital administrator. Facebook and Telegram collection is not configured merely by registering a URL.',
    assistant:'Text, image and voice questions are supported when providers are configured. Voice is transcribed and saved as private conversation text. Raw media is not retained by this application. Listen uses browser speech with a cloud fallback that requires provider model access/terms.',
  }));
  try{
    const catalog=await ai('/models',undefined,5000);
    if(!Array.isArray(catalog.data))throw new Error('Invalid model catalog');
    const active=catalog.data.filter((m:any)=>m.active===true);
    documents.push(doc('system:workspace:models','workspace','Current AI model registry',{
      observed_at:new Date().toISOString(),registry_available:true,active_model_count:active.length,
      models:active.slice(0,30).map((m:any)=>({component:m.component,version:m.version,status:m.metadata?.status??'unknown',data_source:m.metadata?.data_source??'unknown',calibrated:m.metadata?.calibrated??null})),
      complete:active.length<=30,limitations:'An active legacy or synthetic model is not an approved real-data clinical model. Registry access does not test provider connectivity, model accuracy or deployment readiness. No model training or activation occurs through chat.',
    }));
  }catch{documents.push(doc('system:workspace:models','workspace','AI model registry availability',{registry_available:false,observed_at:new Date().toISOString(),limitations:'Current model state could not be checked. Do not infer that models are absent or ready.'}));}
  const metrics=await intelligenceMetrics(hospitalId);
  const {trends,...summary}=metrics;
  documents.push(doc('system:workspace:metrics','workspace','Own hospital verified prediction metrics',{as_of:new Date().toISOString(),...summary}));
  return documents;
}
