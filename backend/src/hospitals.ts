import {referralScope} from './referrals.js';
import {z} from 'zod';
import {db,own,hospitalAdmin,audit,page,type Context} from './app.js';
import {fail,hashPassword} from './security.js';
import * as c from './contracts.js';
import {ai} from './gateway.js';
export const catalogInclude={departments:true,specialties:true,services:true,equipment:true,capacity:true};
export function hospitalRoutes({route}:Context){
  route('POST','/hospitals/register','Request hospital registration',c.registration,async(_r,b)=>{
    const {adminName,adminEmail,password,...profile}=b;
    const hash=await hashPassword(password);
    const hospital=await db.$transaction(async tx=>{
      const hospital=await tx.hospital.create({data:profile});
      const user=await tx.user.create({data:{email:adminEmail,name:adminName,passwordHash:hash,role:'HOSPITAL_ADMIN',active:true,memberships:{create:{hospitalId:hospital.id}}}});
      await tx.auditLog.create({data:{actorId:user.id,hospitalId:hospital.id,action:'HOSPITAL_REGISTERED'}});
      return hospital;
    });return {hospital};
  },'public');
  route('GET','/admin/hospitals','Hospital registrations',null,async r=>({hospitals:await db.hospital.findMany({...page(r.query),orderBy:{createdAt:'desc'}})}),'system');
  route('PATCH','/admin/hospitals/:id','Update registration and status',c.profile.partial().extend({status:z.enum(['PENDING','APPROVED','REJECTED','SUSPENDED']).optional()}),async(r,b)=>{
    const id=(r.params as any).id;
    const hospital=await db.$transaction(async tx=>{const h=await tx.hospital.update({where:{id},data:b});await audit(r.actor,'HOSPITAL_REGISTRATION_UPDATED',id,tx);return h;});return {hospital};
  },'system');
  route('GET','/admin/overview','Platform counts and service availability',null,async()=>{
    const counts=await db.hospital.groupBy({by:['status'],_count:true});
    let health;try{health=await ai('/health');}catch{health={status:'unavailable'};}
    return {counts,ai:health,database:'available'};
  },'system');
  route('GET','/admin/users','Platform account access',null,async r=>({users:await db.user.findMany({...page(r.query),select:{id:true,name:true,email:true,role:true,active:true,memberships:{select:{hospitalId:true}}}})}),'system');
  route('PATCH','/admin/users/:id','Activate or deactivate account',z.object({active:z.boolean()}),async(r,b)=>{
    const id=(r.params as any).id;if(id===r.actor.id&&!b.active)fail(409,'Cannot deactivate your own platform account.');
    await db.$transaction(async tx=>{await tx.user.update({where:{id},data:b});await tx.session.updateMany({where:{userId:id},data:{revokedAt:new Date()}});await audit(r.actor,'ACCOUNT_ACCESS_UPDATED',id,tx);});return {success:true};
  },'system');
  route('GET','/admin/settings','Platform settings',null,async()=>({settings:await db.setting.findMany()}),'system');
  route('POST','/admin/settings','Update platform setting',z.object({key:z.enum(['support_contact','registration_notice']),value:z.string().max(2000)}),async(r,b)=>{await db.$transaction(async tx=>{await tx.setting.upsert({where:{key:b.key},create:b,update:{value:b.value}});await audit(r.actor,'SETTING_UPDATED',b.key,tx);});return {success:true};},'system');
  route('GET','/admin/audit','Platform administration audit trail',null,async r=>({events:await db.auditLog.findMany({where:{hospitalId:null},...page(r.query),orderBy:{createdAt:'desc'}})}),'system');
  route('GET','/workspace','Own hospital workspace',null,async r=>({hospital:await db.hospital.findUnique({where:{id:own(r)},include:catalogInclude})}));
  route('PATCH','/workspace','Update hospital profile',c.profile.partial().omit({registrationNumber:true}),async(r,b)=>{
    hospitalAdmin(r);const hospital=await db.$transaction(async tx=>{const h=await tx.hospital.update({where:{id:own(r)},data:b});await audit(r.actor,'PROFILE_UPDATED',h.id,tx);return h;});return {hospital};
  });
  route('POST','/workspace/catalog','Replace own hospital catalog',c.catalog,async(r,b)=>{
    hospitalAdmin(r);const hospitalId=own(r);
    await db.$transaction(async tx=>{
      await tx.department.deleteMany({where:{hospitalId}});await tx.specialty.deleteMany({where:{hospitalId}});await tx.service.deleteMany({where:{hospitalId}});await tx.equipment.deleteMany({where:{hospitalId}});
      await tx.department.createMany({data:b.departments.map((name:string)=>({hospitalId,name}))});await tx.specialty.createMany({data:b.specialties.map((name:string)=>({hospitalId,name}))});
      await tx.service.createMany({data:b.services.map((x:any)=>({...x,hospitalId}))});await tx.equipment.createMany({data:b.equipment.map((x:any)=>({...x,hospitalId}))});await audit(r.actor,'CATALOG_UPDATED',hospitalId,tx);
    });return {success:true};
  });
  route('POST','/workspace/capacity','Update observed capacity with sharing consent',c.capacity,async(r,b)=>{
    hospitalAdmin(r);const hospitalId=own(r);const capacity=await db.$transaction(async tx=>{
      const data={...b,updatedBy:r.actor.id};const value=await tx.capacity.upsert({where:{hospitalId},create:{...data,hospitalId},update:data});
      await tx.operationalUpdate.create({data:{hospitalId,category:'CAPACITY',content:b,visibility:b.shared?'SHARED':'PRIVATE',source:'Hospital administrator',createdBy:r.actor.id}});await audit(r.actor,'CAPACITY_UPDATED',hospitalId,tx);return value;
    });return {capacity};
  });
  route('GET','/workspace/operations','Operational observations',null,async r=>({updates:await db.operationalUpdate.findMany({where:{hospitalId:own(r)},...page(r.query),orderBy:{createdAt:'desc'}})}));
  route('POST','/workspace/operations','Record operational announcement',c.operation,async(r,b)=>{hospitalAdmin(r);return db.$transaction(async tx=>{const update=await tx.operationalUpdate.create({data:{...b,hospitalId:own(r),createdBy:r.actor.id}});await audit(r.actor,'OPERATION_RECORDED',update.id,tx);return {update};});});
  route('GET','/workspace/users','Hospital members',null,async r=>{hospitalAdmin(r);return {members:await db.membership.findMany({where:{hospitalId:own(r)},...page(r.query),include:{user:{select:{id:true,name:true,email:true,role:true,active:true}}}})};});
  route('POST','/workspace/users','Add hospital user',c.member,async(r,b)=>{
    hospitalAdmin(r);const {permissions,password,...data}=b;const passwordHash=await hashPassword(password);
    const user=await db.$transaction(async tx=>{const u=await tx.user.create({data:{...data,passwordHash,active:true,memberships:{create:{hospitalId:own(r),permissions}}},select:{id:true,email:true,name:true,role:true}});await audit(r.actor,'MEMBER_ADDED',u.id,tx);return u;});return {user};
  });
  route('PATCH','/workspace/users/:id','Change hospital membership permissions',z.object({active:z.boolean(),permissions:z.array(z.enum(['REFERRAL_RECEIVE','REFERRAL_TRIAGE','KNOWLEDGE_REVIEW']))}),async(r,b)=>{
    hospitalAdmin(r);const userId=(r.params as any).id;if(userId===r.actor.id)fail(409,'Cannot change your own membership.');
    await db.$transaction(async tx=>{await tx.membership.update({where:{hospitalId_userId:{hospitalId:own(r),userId}},data:b});await audit(r.actor,'MEMBERSHIP_UPDATED',userId,tx);});return {success:true};
  });
  route('GET','/hospitals','Search authorized hospital directory',null,async r=>{
    const q=z.object({search:z.string().max(200).optional(),location:z.string().max(200).optional(),specialty:z.string().max(200).optional(),service:z.string().max(200).optional()}).parse(r.query);
    const hospitals=await db.hospital.findMany({where:{status:'APPROVED',name:{contains:q.search,mode:'insensitive'},location:{contains:q.location,mode:'insensitive'},...(q.specialty?{specialties:{some:{name:{contains:q.specialty,mode:'insensitive'}}}}:{}),...(q.service?{services:{some:{name:{contains:q.service,mode:'insensitive'},available:true}}}:{})},...page(r.query),include:catalogInclude,orderBy:{name:'asc'}});
    return {hospitals:hospitals.map(h=>({...h,capacity:h.capacity?.shared||h.id===own(r)?h.capacity:null}))};
  });
  route('GET','/workspace/sources','Official external sources',null,async r=>{hospitalAdmin(r);return {sources:await db.externalSource.findMany({where:{hospitalId:own(r)},...page(r.query)})};});
  route('POST','/workspace/sources','Register source; authorization is separate',c.source,async(r,b)=>{hospitalAdmin(r);return db.$transaction(async tx=>{const source=await tx.externalSource.create({data:{...b,hospitalId:own(r)}});await audit(r.actor,'SOURCE_REGISTERED',source.id,tx);return {source};});});
  route('POST','/workspace/sources/:id/collect','Authorize collection of a permitted public source',z.object({permittedPublicAccess:z.literal(true)}),async(r)=>{
    hospitalAdmin(r);const source=await db.externalSource.findFirst({where:{id:(r.params as any).id,hospitalId:own(r)}});if(!source)fail(404,'Source not found.');if(!['WEBSITE','FEED'].includes(source!.kind))fail(400,'Social integrations require provider authorization; no social connector is configured.');
    return db.$transaction(async tx=>{const pending=await tx.sourceJob.findFirst({where:{sourceId:source!.id,status:{in:['PENDING','RUNNING']}}});if(pending)fail(409,'Collection is already queued.');await tx.externalSource.update({where:{id:source!.id},data:{permissionStatus:'PERMITTED_PUBLIC_ACCESS',status:'COLLECTION_QUEUED'}});const job=await tx.sourceJob.create({data:{sourceId:source!.id,hospitalId:own(r),actorId:r.actor.id}});await audit(r.actor,'PUBLIC_SOURCE_COLLECTION_AUTHORIZED',source!.id,tx);return {job};},{isolationLevel:'Serializable'});
  });
  route('GET','/workspace/source-jobs','Public source collection status',null,async r=>{hospitalAdmin(r);return {jobs:await db.sourceJob.findMany({where:{hospitalId:own(r)},...page(r.query),orderBy:{createdAt:'desc'}})};});
  route('GET','/workspace/notifications','Referral notifications',null,async r=>({notifications:await db.notification.findMany({where:{hospitalId:own(r),OR:[{referralId:null},{referralId:{in:(await db.referral.findMany({where:referralScope(r.actor),select:{id:true}})).map(ref=>ref.id)}}]},...page(r.query),orderBy:{createdAt:'desc'}})}));
  route('POST','/workspace/notifications/:id/read','Mark an authorized notification read',null,async r=>{
    const notification=await db.notification.findFirst({where:{id:(r.params as any).id,hospitalId:own(r)}});
    if(!notification||(notification.referralId&&!await db.referral.count({where:{id:notification.referralId,...referralScope(r.actor)}})))fail(404,'Notification not found.');
    await db.notification.update({where:{id:notification!.id},data:{readAt:new Date()}});return {success:true};
  });
  route('GET','/workspace/audit','Own hospital audit trail',null,async r=>{hospitalAdmin(r);return {events:await db.auditLog.findMany({where:{hospitalId:own(r)},...page(r.query),orderBy:{createdAt:'desc'}})};});
}
