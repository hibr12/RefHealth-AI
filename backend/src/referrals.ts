import {z} from 'zod';
import {db,own,hospitalAdmin,audit,page,type Context,type Actor} from './app.js';
import {fail} from './security.js';
import * as c from './contracts.js';
export function referralScope(actor:Actor){const h=actor.hospitalId!;return {OR:[{originId:h},...((actor.role==='HOSPITAL_ADMIN'||actor.permissions.includes('REFERRAL_RECEIVE'))?[{destinationId:h,status:{not:'DRAFT' as const}}]:[])]};}
export async function scopedReferral(actor:Actor,id:string){const referral=await db.referral.findFirst({where:{id,...referralScope(actor)},include:{patient:true,origin:true,destination:true,history:{orderBy:{createdAt:'asc'}},outcome:true}});return referral||fail(404,'Referral not found.');}
export function referralRoutes({route}:Context){
  route('GET','/patients','Own hospital patient identifiers',null,async r=>({patients:await db.patient.findMany({where:{hospitalId:own(r)},...page(r.query),orderBy:{createdAt:'desc'}})}));
  route('POST','/patients','Register patient for referral coordination',c.patient,async(r,b)=>db.$transaction(async tx=>{const patient=await tx.patient.create({data:{...b,hospitalId:own(r)}});await audit(r.actor,'PATIENT_REGISTERED',patient.id,tx);return {patient};}));
  route('GET','/referrals','Authorized incoming and outgoing referrals',null,async r=>({referrals:await db.referral.findMany({where:referralScope(r.actor),...page(r.query),orderBy:{createdAt:'desc'},include:{patient:true,origin:{select:{id:true,name:true}},destination:{select:{id:true,name:true}}}})}));
  route('GET','/referrals/:id','Referral with status history and outcome',null,async r=>({referral:await scopedReferral(r.actor,(r.params as any).id)}));
  route('POST','/referrals','Create draft referral',c.referral,async(r,b)=>{
    if(!await db.patient.findFirst({where:{id:b.patientId,hospitalId:own(r)}}))fail(404,'Patient not found.');
    return db.$transaction(async tx=>{const referral=await tx.referral.create({data:{...b,originId:own(r),createdBy:r.actor.id,history:{create:{status:'DRAFT',actorId:r.actor.id}}}});await audit(r.actor,'REFERRAL_CREATED',referral.id,tx);return {referral};});
  });
  route('POST','/referrals/:id/transition','Submit or process a referral',c.transition,async(r,b)=>{
    const ref=await scopedReferral(r.actor,(r.params as any).id);const h=own(r);
    const transitions:Record<string,string[]>={DRAFT:['SUBMITTED','CANCELLED'],SUBMITTED:['ACCEPTED','REJECTED','CANCELLED'],ACCEPTED:['IN_PROGRESS','CANCELLED'],IN_PROGRESS:['COMPLETED'],REJECTED:[],COMPLETED:[],CANCELLED:[]};
    if(!transitions[ref.status].includes(b.status))fail(409,'Invalid referral status transition.');
    if(b.status==='SUBMITTED'||b.status==='CANCELLED'){if(ref.originId!==h)fail(403,'Only the sending hospital can submit or cancel.');}
    else if(ref.destinationId!==h||(r.actor.role!=='HOSPITAL_ADMIN'&&!r.actor.permissions.includes('REFERRAL_RECEIVE')))fail(403,'Receiving hospital permission required.');
    if(['REJECTED','CANCELLED'].includes(b.status)&&!b.reason?.trim())fail(400,'A reason is required.');
    let destinationId=ref.destinationId;
    let snapshot:any=null;
    if(b.status==='SUBMITTED'){
      if(!b.destinationId||b.destinationId===h)fail(400,'Select another hospital.');
      const destination=await db.hospital.findFirst({where:{id:b.destinationId,status:'APPROVED',services:{some:{name:{equals:ref.requiredService,mode:'insensitive'},available:true}},...(ref.requiredSpecialty?{specialties:{some:{name:{equals:ref.requiredSpecialty,mode:'insensitive'}}}}:{})}});
      if(!destination)fail(400,'Destination does not have the required available service or specialty.');destinationId=destination!.id;
      const capacity=await db.capacity.findUnique({where:{hospitalId:destinationId!}});
      if(capacity?.shared&&Date.now()-capacity.updatedAt.getTime()<=7200000&&[ref.origin.latitude,ref.origin.longitude,destination!.latitude,destination!.longitude].every(v=>v!==null)){
        const rad=(v:number)=>v*Math.PI/180;const dlat=rad(destination!.latitude!-ref.origin.latitude!),dlon=rad(destination!.longitude!-ref.origin.longitude!);const angle=Math.sin(dlat/2)**2+Math.cos(rad(ref.origin.latitude!))*Math.cos(rad(destination!.latitude!))*Math.sin(dlon/2)**2;
        const submitted=new Date(),local=new Date(submitted.getTime()+3*3600000);
        snapshot={hospital_id:destinationId,distance_km:6371*2*Math.atan2(Math.sqrt(angle),Math.sqrt(1-angle)),hospital_workload:capacity.workload,pending_referrals:await db.referral.count({where:{destinationId,status:'SUBMITTED'}}),service_available:1,submission_hour:local.getUTCHours(),submission_day:['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'][local.getUTCDay()],submitted_at:submitted.toISOString(),feature_observed_at:capacity.updatedAt.toISOString(),source_reference:ref.id};
      }
    }
    return db.$transaction(async tx=>{
      const changed=await tx.referral.updateMany({where:{id:ref.id,version:b.version,status:ref.status},data:{status:b.status,destinationId,version:{increment:1}}});if(changed.count!==1)fail(409,'Referral changed. Reload before continuing.');
      await tx.referralHistory.create({data:{referralId:ref.id,status:b.status,reason:b.reason,actorId:r.actor.id}});
      if(snapshot)await tx.operationalUpdate.create({data:{hospitalId:ref.originId,category:'REFERRAL_SNAPSHOT',content:snapshot,source:ref.id,createdBy:r.actor.id}});
      const target=h===ref.originId?destinationId:ref.originId;
      if(target)await tx.notification.create({data:{hospitalId:target,referralId:ref.id,message:`Referral ${ref.id}: ${b.status}`}});
      await audit(r.actor,'REFERRAL_'+b.status,ref.id,tx);return {referral:await tx.referral.findUnique({where:{id:ref.id}})};
    });
  });
  route('POST','/referrals/:id/outcome','Record observed referral outcome',z.object({summary:z.string().min(5).max(4000),actualDelayMinutes:z.number().int().nonnegative()}),async(r,b)=>{
    const ref=await scopedReferral(r.actor,(r.params as any).id);if(ref.status!=='COMPLETED'||ref.destinationId!==own(r))fail(403,'Receiving hospital records outcomes for completed referrals.');
    return db.$transaction(async tx=>{const outcome=await tx.referralOutcome.create({data:{...b,referralId:ref.id,recordedBy:r.actor.id}});await audit(r.actor,'OUTCOME_RECORDED',ref.id,tx);return {outcome};});
  });
  route('POST','/referrals/:id/outcome/verify','Verify an observed outcome',null,async r=>{
    hospitalAdmin(r);const ref=await scopedReferral(r.actor,(r.params as any).id);if(ref.destinationId!==own(r)||!ref.outcome)fail(404,'Outcome not found.');
    await db.$transaction(async tx=>{const updated=await tx.referralOutcome.updateMany({where:{referralId:ref.id,verifiedAt:null},data:{verifiedAt:new Date(),verifiedBy:r.actor.id}});if(!updated.count)fail(409,'Outcome already verified.');await audit(r.actor,'OUTCOME_VERIFIED',ref.id,tx);});return {success:true};
  });
  route('GET','/workspace/overview','Hospital referral and workload statistics',null,async r=>{
    const where=referralScope(r.actor);const counts=await db.referral.groupBy({by:['status'],where,_count:true});
    const [incoming,outgoing,capacity,predictions]=await Promise.all([db.referral.count({where:{AND:[where,{destinationId:own(r)}]}}),db.referral.count({where:{originId:own(r)}}),db.capacity.findUnique({where:{hospitalId:own(r)}}),db.prediction.findMany({where:{hospitalId:own(r),component:'workload'},orderBy:{createdAt:'desc'},take:1})]);
    return {counts,incoming,outgoing,capacity,workloadPrediction:predictions[0]??null};
  });
}
