import {z} from 'zod';
import {Prisma,type ClinicalPriority,type Referral} from '../generated/prisma/index.js';
import {db,own,hospitalAdmin,audit,type Context,type Actor} from './app.js';
import {fail} from './security.js';
import {ai} from './gateway.js';
import * as c from './queue-contracts.js';

type Tx=Prisma.TransactionClient;
const priorities=['CRITICAL','HIGH','MEDIUM','LOW'];
const activeStatuses=['SUBMITTED','ACCEPTED','IN_PROGRESS'] as const;
export const canReceive=(actor:Actor)=>actor.role==='HOSPITAL_ADMIN'||actor.permissions.includes('REFERRAL_RECEIVE');
export const canTriage=(actor:Actor)=>canReceive(actor)&&actor.permissions.includes('REFERRAL_TRIAGE');
function receiving(actor:Actor){if(!actor.hospitalId||!canReceive(actor))fail(403,'Receiving hospital permission required.');return actor.hospitalId!;}
// Queue order is clinician-confirmed only. Suggestions never silently reorder care.
const effective=(r:Pick<Referral,'confirmedPriority'|'aiPriority'>)=>r.confirmedPriority;
const rank=(p:string|null)=>p?priorities.indexOf(p):4;
export const defaultPolicy={timezone:'Africa/Nairobi',deadlines:{},emergencyProcedure:'',protocol:null,version:0};
export function deadlineFields(receivedAt:Date|null,priority:string|null,snapshot:any){
  const setting=snapshot?.deadlines?.[priority??'REVIEW_REQUIRED'];
  if(!receivedAt||!setting)return {acknowledgementDueAt:null,acknowledgementWarningAt:null};
  return {acknowledgementDueAt:new Date(receivedAt.getTime()+setting.minutes*60000),acknowledgementWarningAt:new Date(receivedAt.getTime()+(setting.minutes-setting.warningMinutes)*60000)};
}
export function queueTiming(ref:Pick<Referral,'receivedAt'|'acknowledgedAt'|'acknowledgementDueAt'|'acknowledgementWarningAt'|'status'|'updatedAt'>,now=new Date()){
  const closed=!activeStatuses.includes(ref.status as any);
  const end=ref.acknowledgedAt??(closed?ref.updatedAt:now);
  const acknowledgementStatus=ref.acknowledgedAt?'ACKNOWLEDGED':closed?'CLOSED':!ref.receivedAt?'ARRIVAL_UNKNOWN':!ref.acknowledgementDueAt?'UNCONFIGURED':now>=ref.acknowledgementDueAt?'OVERDUE':ref.acknowledgementWarningAt&&now>=ref.acknowledgementWarningAt?'APPROACHING':'WAITING';
  return {waitingSeconds:ref.receivedAt?Math.max(0,Math.floor((end.getTime()-ref.receivedAt.getTime())/1000)):null,acknowledgementStatus};
}
export async function queueEvent(tx:Tx,referralId:string,kind:string,reason:string,actorId?:string,extra:Record<string,unknown>={}){
  return tx.referralQueueEvent.create({data:{referralId,kind,reason,actorId,...extra}});
}
export async function recordArrival(tx:Tx,ref:Referral,actor:Actor){
  const policy=await tx.queuePolicy.findUnique({where:{hospitalId:ref.destinationId!}})??defaultPolicy;
  const snapshot={timezone:policy.timezone,deadlines:policy.deadlines,emergencyProcedure:policy.emergencyProcedure,version:policy.version};
  // A separate receipt event at the destination, after the submission write, in the same atomic delivery.
  const [clock]=await tx.$queryRaw<{now:Date}[]>`SELECT clock_timestamp() AS now`;
  const receivedAt=clock.now;
  await tx.referral.update({where:{id:ref.id},data:{receivedAt,queuePolicySnapshot:snapshot,assessmentStatus:policy.protocol?'PENDING':'DISABLED',...deadlineFields(receivedAt,null,snapshot)}});
  await queueEvent(tx,ref.id,'ARRIVED','Delivered to the receiving hospital queue.',actor.id,{details:{receivedAt:receivedAt.toISOString(),policy:snapshot}});
  if(!policy.protocol)await queueEvent(tx,ref.id,'PRIORITIZATION_DISABLED','No approved, clinically validated protocol supplied. Authorized clinician assignment is required.');
}
export async function recordAcknowledgement(tx:Tx,ref:Referral,actor:Actor){
  if(ref.acknowledgedAt)return;
  const [clock]=await tx.$queryRaw<{now:Date}[]>`SELECT clock_timestamp() AS now`;
  const changed=await tx.referral.updateMany({where:{id:ref.id,acknowledgedAt:null},data:{acknowledgedAt:clock.now,acknowledgedBy:actor.id}});
  if(changed.count)await queueEvent(tx,ref.id,'ACKNOWLEDGED','Receiving hospital acknowledged receipt.',actor.id,{details:{acknowledgedAt:clock.now.toISOString()}});
}
async function incomingReferral(actor:Actor,id:string){
  const ref=await db.referral.findFirst({where:{id,destinationId:receiving(actor),status:{not:'DRAFT'}}});
  return ref??fail(404,'Incoming referral not found.');
}

const assessmentResult=z.object({priority:c.priority.nullable(),requires_review:z.literal(true),protocol_version:z.string().nullable(),matched_rules:z.array(z.string()).max(100),factors:z.array(z.object({field:z.string(),operator:z.string(),value:z.union([z.string(),z.number()]),unit:z.string().nullable()})).max(20),missing_fields:z.array(z.string()).max(200),explanation:z.string().min(1).max(4000)}).strict();
export async function assessReferral(id:string,actorId?:string,expectedVersion?:number){
  const ref=await db.referral.findUnique({where:{id}});
  if(!ref||!ref.destinationId||!activeStatuses.includes(ref.status as any))return null;
  if(expectedVersion!==undefined&&ref.version!==expectedVersion)fail(409,'Referral changed. Reload before requesting a recommendation.');
  const policy=await db.queuePolicy.findUnique({where:{hospitalId:ref.destinationId}});
  let result:z.infer<typeof assessmentResult>={priority:null,requires_review:true,protocol_version:null,matched_rules:[],factors:[],missing_fields:[],explanation:'No approved clinical protocol is configured. Clinical review is required.'};
  let assessmentStatus='DISABLED';
  if(policy?.protocol){
    try{
      const protocol=c.protocol.parse(policy.protocol);
      const response=await ai('/integration/clinical-priority',{urgency:ref.urgency,requiredService:ref.requiredService,requiredSpecialty:ref.requiredSpecialty,observations:c.clinicalObservations.parse(ref.clinicalObservations),protocol},5000);
      result=assessmentResult.parse(response.data);
      if(response.engine!=='approved-protocol-rules-v1'||result.protocol_version!==protocol.version||result.matched_rules.some(id=>!protocol.rules.some(rule=>rule.id===id))||(result.priority&&!protocol.rules.some(rule=>result.matched_rules.includes(rule.id)&&rule.priority===result.priority)))throw new Error('Invalid protocol result');
      assessmentStatus=result.priority?'RECOMMENDED':'REVIEW_REQUIRED';
    }catch{
      result={...result,priority:null,explanation:'Clinical prioritization service is unavailable or returned an invalid result. Clinical review is required; the referral remains available.'};
      assessmentStatus='UNAVAILABLE';
    }
  }
  return db.$transaction(async tx=>{
    // Lock through the version update: an older assessment cannot overwrite a clinician's concurrent review.
    const p=ref.confirmedPriority;
    const changed=await tx.referral.updateMany({where:{id,version:ref.version,status:ref.status},data:{aiPriority:result.priority,priorityRank:rank(p),priorityExplanation:result.explanation,assessmentStatus,assessedAt:new Date(),version:{increment:1},...(!ref.acknowledgedAt?deadlineFields(ref.receivedAt,p,ref.queuePolicySnapshot):{})}});
    if(!changed.count){if(actorId)fail(409,'Referral changed during assessment. Reload and review.');return null;}
    await queueEvent(tx,id,'AI_RECOMMENDATION',result.explanation,actorId,{previousPriority:ref.aiPriority,priority:result.priority,details:{engine:'approved-protocol-rules-v1',...result,protocol:policy?.protocol??null,policyVersion:policy?.version??0}});
    return tx.referral.findUnique({where:{id}});
  });
}

export async function monitorAcknowledgements(now=new Date(),hospitalId?:string){
  const candidates=await db.referral.findMany({where:{...(hospitalId?{destinationId:hospitalId}:{}),destination:{status:'APPROVED'},status:'SUBMITTED',acknowledgedAt:null,OR:[{overdueNotifiedAt:null,acknowledgementDueAt:{lte:now}},{warningNotifiedAt:null,acknowledgementWarningAt:{lte:now}}]},orderBy:[{acknowledgementDueAt:'asc'},{id:'asc'}],take:200});
  for(const ref of candidates){
    const overdue=!!ref.acknowledgementDueAt&&ref.acknowledgementDueAt<=now;
    // An overdue alert supersedes an approaching alert, without changing clinical priority.
    const flag=overdue?'overdueNotifiedAt':'warningNotifiedAt';
    if(ref[flag])continue;
    await db.$transaction(async tx=>{
      const changed=await tx.referral.updateMany({where:{id:ref.id,version:ref.version,status:'SUBMITTED',acknowledgedAt:null,[flag]:null},data:{[flag]:now,...(overdue&&!ref.warningNotifiedAt?{warningNotifiedAt:now}:{})}});
      if(!changed.count)return;
      const kind=overdue?'ACKNOWLEDGEMENT_OVERDUE':'ACKNOWLEDGEMENT_APPROACHING';
      const reason=overdue?'The configured acknowledgement deadline was exceeded.':'The configured acknowledgement deadline is approaching.';
      await queueEvent(tx,ref.id,kind,reason,undefined,{priority:effective(ref),details:{deadline:ref.acknowledgementDueAt?.toISOString(),policy:ref.queuePolicySnapshot}});
      await tx.notification.create({data:{hospitalId:ref.destinationId!,referralId:ref.id,message:`Referral ${ref.id}: ${reason} Clinical priority is unchanged.`}});
    });
  }
}
export async function processPriorityRecommendations(){
  const refs=await db.referral.findMany({where:{assessmentStatus:'PENDING',status:{in:[...activeStatuses]},destination:{status:'APPROVED'}},orderBy:[{receivedAt:'asc'},{id:'asc'}],take:10});
  for(const ref of refs)await assessReferral(ref.id);
}

export function incomingQueueRoutes({route}:Context){
  route('GET','/incoming/policy','Receiving hospital queue policy',null,async r=>{receiving(r.actor);return {policy:await db.queuePolicy.findUnique({where:{hospitalId:own(r)}})??defaultPolicy};});
  route('POST','/incoming/policy','Configure hospital deadlines and approved clinical protocol',c.queuePolicy,async(r,b)=>{
    hospitalAdmin(r);
    return db.$transaction(async tx=>{
      const {version,...values}=b;
      const data={...values,protocol:values.protocol??Prisma.DbNull,updatedBy:r.actor.id};
      const prior=await tx.queuePolicy.findUnique({where:{hospitalId:own(r)}});
      if(prior){const changed=await tx.queuePolicy.updateMany({where:{hospitalId:own(r),version},data:{...data,version:{increment:1}}});if(!changed.count)fail(409,'Queue policy changed. Reload before saving.');}
      else {if(version!==0)fail(409,'Queue policy changed.');await tx.queuePolicy.create({data:{...data,hospitalId:own(r),version:1}});}
      // Immutable policy revisions retain the approval evidence and complete rule definitions.
      await tx.operationalUpdate.create({data:{hospitalId:own(r),category:'QUEUE_POLICY',content:{...b,version:version+1},source:'Hospital-approved queue policy',createdBy:r.actor.id}});
      await audit(r.actor,'QUEUE_POLICY_CHANGED',own(r),tx);
      return {policy:await tx.queuePolicy.findUnique({where:{hospitalId:own(r)}})};
    });
  });
  route('GET','/incoming','Incoming referrals ordered by clinical priority then receipt time',null,async r=>{
    const hospitalId=receiving(r.actor),q=c.queueQuery.parse(r.query),now=new Date();
    const where:Prisma.ReferralWhereInput={destinationId:hospitalId,status:q.status==='ALL'?{not:'DRAFT'}:q.status??{in:[...activeStatuses]}};
    if(q.priority)where.priorityRank=q.priority==='REVIEW_REQUIRED'?4:rank(q.priority);
    if(q.review)where.confirmedPriority=null;
    if(q.originId)where.originId=q.originId;
    if(q.service)where.requiredService={contains:q.service,mode:'insensitive'};
    if(q.acknowledged)where.acknowledgedAt=q.acknowledged==='yes'?{not:null}:null;
    if(q.sort==='waiting'){where.acknowledgedAt=null;where.AND=[{status:'SUBMITTED'}];}
    if(q.overdue){where.acknowledgedAt=null;where.acknowledgementDueAt={lte:now};where.AND=[{status:'SUBMITTED'}];}
    if(q.arrivedFrom||q.arrivedTo||q.minWaitingMinutes!==undefined){
      // Waiting duration is frozen at acknowledgement/closure; elapsed arrival age is a distinct measure.
      const constraints:Prisma.ReferralWhereInput[]=[];
      if(q.arrivedFrom||q.arrivedTo)constraints.push({receivedAt:{...(q.arrivedFrom?{gte:new Date(q.arrivedFrom)}:{}),...(q.arrivedTo?{lte:new Date(q.arrivedTo)}:{})}});
      if(q.minWaitingMinutes!==undefined){where.acknowledgedAt=null;constraints.push({status:'SUBMITTED',receivedAt:{lte:new Date(now.getTime()-q.minWaitingMinutes*60000)}});}
      where.AND=[...(Array.isArray(where.AND)?where.AND:[]),...constraints];
    }
    const orderBy:Prisma.ReferralOrderByWithRelationInput[]=[...(q.sort==='priority'?[{priorityRank:'asc' as const}]:[]),{receivedAt:{sort:'asc',nulls:'last'}},{id:'asc'}];
    const [referrals,total,unreviewed,policy,facilities,services,forecast]=await db.$transaction([
      db.referral.findMany({where,orderBy,skip:(q.page-1)*q.limit,take:q.limit,include:{patient:true,origin:{select:{id:true,name:true}}}}),
      db.referral.count({where}),db.referral.count({where:{destinationId:hospitalId,status:{in:[...activeStatuses]},confirmedPriority:null}}),
      db.queuePolicy.findUnique({where:{hospitalId}}),
      db.referral.findMany({where:{destinationId:hospitalId,status:{not:'DRAFT'}},distinct:['originId'],select:{origin:{select:{id:true,name:true}}}}),
      db.referral.findMany({where:{destinationId:hospitalId,status:{not:'DRAFT'}},distinct:['requiredService'],select:{requiredService:true}}),
      db.prediction.findFirst({where:{hospitalId,component:'workload'},orderBy:{createdAt:'desc'},select:{result:true,createdAt:true,modelVersionId:true}}),
    ],{isolationLevel:'RepeatableRead'});
    // Reuse the sender's saved recommendation only for this selected destination; never expose other candidates or patients.
    const saved=await db.prediction.findMany({where:{referralId:{in:referrals.map(ref=>ref.id)},component:'recommendation'},orderBy:{createdAt:'desc'},select:{referralId:true,result:true,createdAt:true,modelVersionId:true}});
    return {referrals:referrals.map(ref=>{
      const prediction=saved.find(p=>p.referralId===ref.id),candidate=(prediction?.result as any)?.ranked_hospitals?.find((h:any)=>h.hospital_id===hospitalId);
      return {...ref,effectivePriority:effective(ref),requiresClinicalReview:!ref.confirmedPriority,...queueTiming(ref,now),delayPrediction:candidate?.delay_prediction?{result:candidate.delay_prediction,createdAt:prediction!.createdAt,modelVersionId:prediction!.modelVersionId}:null};
    }),total,page:q.page,limit:q.limit,unreviewed,policy:policy??defaultPolicy,facilities:facilities.map(f=>f.origin),services:services.map(s=>s.requiredService),workloadPrediction:forecast,serverTime:now.toISOString()};
  });
  route('POST','/incoming/:id/acknowledge','Acknowledge receipt independently of acceptance',c.versionBody,async(r,b)=>{
    const ref=await incomingReferral(r.actor,(r.params as any).id);
    if(ref.acknowledgedAt)return {referral:ref};
    if(ref.status!=='SUBMITTED')fail(409,'Only a pending incoming referral can be acknowledged.');
    return db.$transaction(async tx=>{
      const changed=await tx.referral.updateMany({where:{id:ref.id,version:b.version,status:'SUBMITTED',acknowledgedAt:null},data:{version:{increment:1}}});
      if(!changed.count)fail(409,'Referral changed. Reload before acknowledging.');
      await recordAcknowledgement(tx,ref,r.actor);await audit(r.actor,'REFERRAL_ACKNOWLEDGED',ref.id,tx);
      return {referral:await tx.referral.findUnique({where:{id:ref.id}})};
    });
  });
  route('POST','/incoming/:id/priority','Confirm or override clinical priority with a reason',c.priorityReview,async(r,b)=>{
    const ref=await incomingReferral(r.actor,(r.params as any).id);
    if(!canTriage(r.actor))fail(403,'Clinical priority review permission required.');
    if(!activeStatuses.includes(ref.status as any))fail(409,'This referral is closed.');
    return db.$transaction(async tx=>{
      const changed=await tx.referral.updateMany({where:{id:ref.id,version:b.version,status:ref.status},data:{confirmedPriority:b.priority,confirmedBy:r.actor.id,confirmedAt:new Date(),priorityRank:rank(b.priority),version:{increment:1},...(!ref.acknowledgedAt?deadlineFields(ref.receivedAt,b.priority,ref.queuePolicySnapshot):{})}});
      if(!changed.count)fail(409,'Referral changed. Reload before reviewing priority.');
      const kind=ref.confirmedPriority?'PRIORITY_CHANGED':ref.aiPriority===b.priority?'PRIORITY_CONFIRMED':'PRIORITY_OVERRIDDEN';
      await queueEvent(tx,ref.id,kind,b.reason,r.actor.id,{previousPriority:effective(ref),priority:b.priority,details:{aiPriority:ref.aiPriority}});
      await audit(r.actor,kind,ref.id,tx);
      return {referral:await tx.referral.findUnique({where:{id:ref.id}})};
    });
  });
  route('POST','/incoming/:id/recommendation','Reassess using the current approved hospital protocol',c.versionBody,async(r,b)=>{
    const ref=await incomingReferral(r.actor,(r.params as any).id);
    if(!canTriage(r.actor))fail(403,'Clinical priority review permission required.');
    if(!activeStatuses.includes(ref.status as any))fail(409,'This referral is closed.');
    return {referral:await assessReferral(ref.id,r.actor.id,b.version)};
  });
  route('GET','/incoming/:id/events','Receiving hospital priority, arrival, acknowledgement and escalation audit',null,async r=>{
    const ref=await incomingReferral(r.actor,(r.params as any).id);
    const q=z.object({page:z.coerce.number().int().positive().default(1),limit:z.coerce.number().int().min(1).max(100).default(50)}).parse(r.query);
    return {events:await db.referralQueueEvent.findMany({where:{referralId:ref.id},orderBy:[{createdAt:'desc'},{id:'desc'}],take:q.limit,skip:(q.page-1)*q.limit}),total:await db.referralQueueEvent.count({where:{referralId:ref.id}})};
  });
}
