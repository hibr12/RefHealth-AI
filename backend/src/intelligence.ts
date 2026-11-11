import {z} from 'zod';
import {db,own,hospitalAdmin,audit,page,type Context} from './app.js';
import {fail,digest} from './security.js';
import {timingSafeEqual} from 'node:crypto';
import {config} from './config.js';
import {ai} from './gateway.js';
import {scopedReferral,referralScope} from './referrals.js';
import {catalogInclude} from './hospitals.js';
import {intelligenceMetrics} from './metrics.js';
import {assistantContext} from './assistant-context.js';
import {assistantThreadRoutes,ownedThread,threadScope,publicConversation} from './assistant-threads.js';
import * as c from './contracts.js';
const publicKnowledge=(hospitalId:string)=>({status:'APPROVED' as const,OR:[{hospitalId},{visibility:{in:['PUBLIC' as const,'SHARED' as const]}}],hospital:{status:'APPROVED' as const}});
async function savePrediction(hospitalId:string,component:string,result:any,referralId?:string){
  if(typeof result.model_version!=='string'||!result.data||typeof result.data!=='object')fail(502,'AI response is missing prediction metadata.');
  return db.$transaction(async tx=>{
    await tx.modelVersion.upsert({where:{id:result.model_version},create:{id:result.model_version,component,metadata:{source:'AI service',limitations:result.data.limitations??[]}},update:{}});
    return tx.prediction.create({data:{hospitalId,referralId,component,modelVersionId:result.model_version,result:result.data}});
  });
}
function distance(a:any,b:any){
  if([a.latitude,a.longitude,b.latitude,b.longitude].some(v=>v==null))return null;
  const radians=(n:number)=>n*Math.PI/180;const dlat=radians(b.latitude-a.latitude),dlon=radians(b.longitude-a.longitude);
  const v=Math.sin(dlat/2)**2+Math.cos(radians(a.latitude))*Math.cos(radians(b.latitude))*Math.sin(dlon/2)**2;return 6371*2*Math.atan2(Math.sqrt(v),Math.sqrt(1-v));
}
export function intelligenceRoutes({route}:Context){
  assistantThreadRoutes({route});
  route('GET','/internal/learning-export','Service-only export of verified patient-free training observations',null,async r=>{
    const key=String(r.headers['x-api-key']||'');if(!config.AI_SERVICE_KEY||!timingSafeEqual(Buffer.from(digest(key)),Buffer.from(digest(config.AI_SERVICE_KEY))))fail(401,'Service authentication required.');
    const query=z.object({kind:z.enum(['daily','referrals']),cursor:z.string().optional()}).parse(r.query);
    const records=await db.operationalUpdate.findMany({where:{category:query.kind==='daily'?'DAILY_VERIFIED':'REFERRAL_SNAPSHOT',hospital:{status:'APPROVED'}},orderBy:{id:'asc'},take:100,...(query.cursor?{cursor:{id:query.cursor},skip:1}:{})});
    const exported=[];
    for(const row of records){
      if(query.kind==='daily')exported.push({id:row.id,payload:row.content,source_reference:row.source,verified_by:row.createdBy,verified_at:row.createdAt.toISOString()});
      else{const referral=await db.referral.findUnique({where:{id:row.source},include:{outcome:true,history:{where:{status:{in:['ACCEPTED','REJECTED']}},orderBy:{createdAt:'asc'},take:1}}});if(referral?.outcome?.verifiedAt&&referral.history[0])exported.push({id:row.id,payload:row.content,acknowledged_at:referral.history[0].createdAt.toISOString(),verified_by:referral.outcome.verifiedBy,verified_at:referral.outcome.verifiedAt.toISOString()});}
    }
    return {records:exported,nextCursor:records.length===100?records[records.length-1].id:null};
  },'public');
  route('POST','/referrals/:id/intelligence','Request ranked hospitals for a saved referral',null,async r=>{
    const ref=await scopedReferral(r.actor,(r.params as any).id);if(ref.originId!==own(r))fail(403,'Sending hospital access required.');
    const hospitals=await db.hospital.findMany({where:{status:'APPROVED',id:{not:own(r)}},include:catalogInclude});
    const candidates=await Promise.all(hospitals.map(async h=>{
      const authorizedCapacity=h.capacity?.shared?h.capacity:null;
      const outcomes=await db.referral.findMany({where:{destinationId:h.id,status:{in:['ACCEPTED','REJECTED','IN_PROGRESS','COMPLETED']}},select:{status:true,outcome:{select:{actualDelayMinutes:true,verifiedAt:true}}}});
      const verified=outcomes.filter(x=>x.outcome?.verifiedAt);
      const history=await db.operationalUpdate.findMany({where:{hospitalId:h.id,category:'DAILY_VERIFIED',visibility:{in:['SHARED','PUBLIC']}},orderBy:{createdAt:'desc'},take:7});
      return {hospital_id:h.id,hospital_name:h.name,specialties:h.specialties.map(x=>x.name),services:h.services.map(x=>({name:x.name,available:x.available})),distance_km:distance(ref.origin,h),capacity:authorizedCapacity?{available_beds:authorizedCapacity.availableBeds,total_beds:authorizedCapacity.totalBeds,workload:authorizedCapacity.workload,updated_at:authorizedCapacity.updatedAt.toISOString()}:null,
        pending_referrals:authorizedCapacity?await db.referral.count({where:{destinationId:h.id,status:'SUBMITTED'}}):null,
        acceptance_rate:authorizedCapacity&&outcomes.length>=10?outcomes.filter(x=>x.status!=='REJECTED').length/outcomes.length:null,
        processing_minutes:authorizedCapacity&&verified.length>=10?verified.reduce((sum,x)=>sum+x.outcome!.actualDelayMinutes,0)/verified.length:null,workload_history:history.length===7?history.map(x=>x.content):null};
    }));
    const result=await ai('/integration/recommend',{required_service:ref.requiredService,required_specialty:ref.requiredSpecialty,source_hospital_id:own(r),candidates});
    const ranking=z.object({ranked_hospitals:z.array(z.object({hospital_id:z.string(),hospital_name:z.string(),suitability_score:z.number().min(0).max(100),rank:z.number().int().positive(),reasons:z.array(z.string()),limitations:z.array(z.string())}).passthrough()),excluded:z.array(z.object({hospital_id:z.string(),reason:z.string()})),limitations:z.array(z.string())}).passthrough().safeParse(result.data);
    if(!ranking.success||ranking.data.ranked_hospitals.some(h=>!candidates.some(c=>c.hospital_id===h.hospital_id)))fail(502,'AI ranking response is invalid.');
    const prediction=await savePrediction(own(r),'recommendation',result,ref.id);await audit(r.actor,'AI_RECOMMENDATION',prediction.id);return {prediction};
  });
  route('POST','/workspace/workload','Forecast own hospital workload from observed history',z.object({asOfDate:z.string().date()}),async(r,b)=>{
    const records=await db.operationalUpdate.findMany({where:{hospitalId:own(r),category:'DAILY_VERIFIED'},orderBy:{createdAt:'desc'},take:366});
    const history=records.map(x=>x.content as Record<string,unknown>)
      .filter(x=>typeof x.record_date==='string'&&x.record_date<=b.asOfDate);
    if(history.length<7)fail(503,'At least seven verified daily records through the selected date are required for a workload forecast.');
    const result=await ai('/integration/workload',{hospital_id:own(r),as_of_date:b.asOfDate,history});
    return {prediction:await savePrediction(own(r),'workload',result)};
  });
  route('POST','/workspace/daily','Record verified finalized daily workload',z.object({record_date:z.string().date(),patient_volume:z.number().int().nonnegative(),incoming_referrals:z.number().int().nonnegative(),pending_referrals:z.number().int().nonnegative(),available_beds:z.number().int().nonnegative(),total_beds:z.number().int().positive(),workload_level:z.enum(['Low','Medium','High']),source_reference:c.text,shared:z.boolean().default(false)}).refine(b=>b.available_beds<=b.total_beds,'Invalid bed count'),async(r,b)=>{
    hospitalAdmin(r);if(b.record_date>=new Date().toISOString().slice(0,10))fail(400,'Daily records must describe a completed day.');
    const {source_reference,shared,...measurements}=b;
    return db.$transaction(async tx=>{const prior=await tx.operationalUpdate.findFirst({where:{hospitalId:own(r),category:'DAILY_VERIFIED',content:{path:['record_date'],equals:b.record_date}}});if(prior)fail(409,'Daily record already exists.');const update=await tx.operationalUpdate.create({data:{hospitalId:own(r),category:'DAILY_VERIFIED',content:{...measurements,hospital_id:own(r)},source:source_reference,createdBy:r.actor.id,visibility:shared?'SHARED':'PRIVATE'}});await audit(r.actor,'DAILY_OBSERVATION_VERIFIED',update.id,tx);return {update};},{isolationLevel:'Serializable'});
  });
  route('GET','/intelligence','Own hospital AI predictions and verified outcomes',null,async r=>({predictions:await db.prediction.findMany({where:{hospitalId:own(r)},...page(r.query),orderBy:{createdAt:'desc'},include:{feedback:true,modelVersion:true,referral:{select:{outcome:true,status:true}}}}),observations:await db.operationalUpdate.findMany({where:{hospitalId:own(r),category:{in:['CAPACITY','DAILY_VERIFIED']}},take:100,orderBy:{createdAt:'desc'}})}));
  route('GET','/intelligence/metrics','Hospital-level verified prediction metrics',null,async r=>intelligenceMetrics(own(r)));
  route('POST','/predictions/:id/feedback','Submit unverified prediction feedback',z.object({rating:z.number().int().min(1).max(5),comment:z.string().min(3).max(2000)}),async(r,b)=>{
    const id=(r.params as any).id;if(!await db.prediction.findFirst({where:{id,hospitalId:own(r)}}))fail(404,'Prediction not found.');
    return db.$transaction(async tx=>{const feedback=await tx.feedback.create({data:{...b,predictionId:id,hospitalId:own(r),userId:r.actor.id}});await audit(r.actor,'AI_FEEDBACK',feedback.id,tx);return {feedback};});
  });
  route('GET','/knowledge','Approved authorized knowledge and own proposals',null,async r=>({records:await db.knowledgeRecord.findMany({where:{OR:[publicKnowledge(own(r)),{hospitalId:own(r)}]},...page(r.query),orderBy:{updatedAt:'desc'},include:{approval:true}})}));
  route('POST','/knowledge','Propose a knowledge update',c.knowledge,async(r,b)=>{
    if(b.conversationId&&!await db.conversation.findFirst({where:{id:b.conversationId,hospitalId:own(r),userId:r.actor.id}}))fail(404,'Conversation not found.');
    return db.$transaction(async tx=>{const record=await tx.knowledgeRecord.create({data:{...b,hospitalId:own(r),createdBy:r.actor.id}});await audit(r.actor,'KNOWLEDGE_PROPOSED',record.id,tx);return {record};});
  });
  route('POST','/knowledge/:id/review','Approve or reject own hospital knowledge',z.object({decision:z.enum(['APPROVED','REJECTED']),reason:z.string().min(3).max(2000)}),async(r,b)=>{
    if(r.actor.role!=='HOSPITAL_ADMIN'&&!r.actor.permissions.includes('KNOWLEDGE_REVIEW'))fail(403,'Knowledge review permission required.');
    const id=(r.params as any).id;await db.$transaction(async tx=>{
      const record=await tx.knowledgeRecord.updateMany({where:{id,hospitalId:own(r),status:'PENDING'},data:{status:b.decision}});if(!record.count)fail(409,'Proposal is missing or already reviewed.');
      await tx.knowledgeApproval.create({data:{knowledgeId:id,reviewerId:r.actor.id,...b}});await audit(r.actor,'KNOWLEDGE_'+b.decision,id,tx);
    });return {success:true};
  });
  route('GET','/assistant/conversations','Private conversation history (legacy flat view)',null,async r=>({conversations:(await db.conversation.findMany({where:{hospitalId:own(r),userId:r.actor.id},...page(r.query),orderBy:[{createdAt:'desc'},{id:'desc'}]})).map(publicConversation)}));
  route('POST','/assistant/speech','Read a segment of your own saved assistant reply',z.object({conversationId:c.text,offset:z.number().int().nonnegative().max(20000).default(0)}),async(r,b)=>{
    const conversation=await db.conversation.findFirst({where:{id:b.conversationId,hospitalId:own(r),userId:r.actor.id},select:{answer:true}});
    if(!conversation)return fail(404,'Conversation not found.');
    if(b.offset>=conversation.answer.length)fail(400,'Speech offset is outside this reply.');
    const segment=conversation.answer.slice(b.offset,b.offset+200),boundary=segment.lastIndexOf(' ');
    const text=segment.length===200&&boundary>=100?segment.slice(0,boundary+1):segment;
    const result=await ai('/integration/speech',{text},config.AI_ASSISTANT_TIMEOUT_MS);
    const audio=z.object({mime_type:z.literal('audio/wav'),audio:z.string().min(60).max(11_184_812).regex(/^[A-Za-z0-9+/]+={0,2}$/)}).safeParse(result.data);
    if(!audio.success)fail(502,'The speech provider returned invalid audio.');
    return {...audio.data,nextOffset:b.offset+text.length<conversation.answer.length?b.offset+text.length:null};
  });
  const chatAttachment=z.object({
    mime_type:z.enum(['image/jpeg','image/png','image/webp','image/gif','audio/wav','audio/mp3','audio/mpeg','audio/aiff','audio/aac','audio/ogg','audio/flac','audio/m4a','audio/mp4','audio/opus','audio/webm']),
    data:z.string().min(4).max(5_600_000).refine(value=>value.length%4===0&&/^[A-Za-z0-9+/]*={0,2}$/.test(value),'Attachment must be base64 encoded.')
  }).optional();
  const chatHistory=z.array(z.object({role:z.enum(['user','assistant']),content:z.string().min(1).max(20000)}).transform(turn=>({...turn,content:turn.content.slice(-4000)}))).max(16).default([]);
  route('POST','/assistant/chat','Answer in your saved chat using authorized hospital information',z.object({question:z.string().trim().min(1).max(2000),referralId:c.text.optional(),threadId:z.string().uuid().optional(),expectedVersion:z.number().int().nonnegative().optional(),clientRequestId:z.string().uuid().optional(),history:chatHistory,attachment:chatAttachment}),async(r,b)=>{
    const scope=threadScope(r.actor),requestDigest=digest(JSON.stringify({threadId:b.threadId??null,question:b.question,referralId:b.referralId??null,attachment:b.attachment??null}));
    const completed=async()=>{
      if(!b.clientRequestId)return null;
      const saved=await db.conversation.findFirst({where:{...scope,clientRequestId:b.clientRequestId},include:{thread:true}});
      if(!saved)return null;
      if(saved.requestDigest!==requestDigest)return fail(409,'This message request was already used. Start a new request.');
      const {thread,...row}=saved;return {conversation:publicConversation(row),thread};
    };
    const replay=await completed();if(replay)return replay;
    const thread=b.threadId?await ownedThread(r.actor,b.threadId):null;
    if(thread&&b.expectedVersion!==undefined&&thread.version!==b.expectedVersion)fail(409,'This chat has a newer reply. Reload it before sending again.');
    const previous=thread?await db.conversation.findMany({where:{threadId:thread.id,...scope},orderBy:{sequence:'desc'},take:8,select:{question:true,answer:true}}):[];
    // Only persisted turns from this owned thread form AI history. The legacy
    // history input remains accepted, but can no longer mix or forge chat context.
    const history=previous.reverse().flatMap(turn=>[{role:'user',content:turn.question.slice(-4000)},{role:'assistant',content:turn.answer.slice(-4000)}]);
    const documents=await assistantContext(r.actor,b.referralId);
    const result=await ai('/integration/assistant',{question:b.question,hospital_id:own(r),documents,history,attachment:b.attachment},config.AI_ASSISTANT_TIMEOUT_MS);
    const parsed=z.object({answer:z.string(),sources:z.array(z.object({id:z.string(),source:z.string(),updated_at:z.string()}).passthrough()),proposals:z.array(z.object({category:c.text,content:z.string().min(3).max(4000)})).default([]),transcript:z.string().trim().min(1).max(4000).optional(),user_message:z.string().trim().min(1).max(6100).optional()}).parse(result.data);
    // Reconstruct citations from this request's authorized context. Provider text
    // cannot introduce a new source or replace its content/attribution.
    const allowed=new Map(documents.map(d=>[d.id,d]));
    if(parsed.sources.some(source=>!allowed.has(source.id)))fail(502,'The assistant cited information outside the authorized workspace.');
    const sources=[...new Set(parsed.sources.map(s=>s.id))].map(id=>{const d=allowed.get(id)!;return {id:d.id,hospital_id:d.hospital_id,category:d.category,source:d.source,updated_at:d.updated_at,content:d.content,stale:!!d.review_at&&new Date(d.review_at)<new Date()};});
    const isAudio=b.attachment?.mime_type.startsWith('audio/');
    if(isAudio&&(!parsed.transcript||!parsed.user_message))fail(502,'The voice response is missing its transcription. Please try again.');
    try{return await db.$transaction(async tx=>{
      const question=isAudio?parsed.user_message!:b.question;
      let savedThread;
      if(thread){
        const updated=await tx.chatThread.updateMany({where:{id:thread.id,...scope,version:thread.version},data:{version:{increment:1},updatedAt:new Date()}});
        if(!updated.count)fail(409,'This chat received another reply. Reload it before sending again.');
        savedThread=await tx.chatThread.findUniqueOrThrow({where:{id:thread.id}});
      }else savedThread=await tx.chatThread.create({data:{...scope,title:question.replace(/\s+/g,' ').slice(0,80),version:1}});
      const conversation=await tx.conversation.create({data:{...scope,threadId:savedThread.id,sequence:savedThread.version,question,answer:parsed.answer,sources,attachmentKind:b.attachment?(isAudio?'audio':'image'):null,clientRequestId:b.clientRequestId,requestDigest:b.clientRequestId?requestDigest:null}});
      for(const proposal of parsed.proposals)await tx.knowledgeRecord.create({data:{hospitalId:own(r),conversationId:conversation.id,category:proposal.category,content:proposal.content,source:'Unverified conversation extraction',createdBy:r.actor.id}});
      await audit(r.actor,'ASSISTANT_CONVERSATION',conversation.id,tx);return {conversation:publicConversation(conversation),thread:savedThread};
    });}catch(error){const replay=await completed();if(replay)return replay;throw error;}
  },'hospital',{bodyLimit:6*1024*1024});
  route('GET','/ai/health','AI model availability',null,async()=>ai('/health'));
  route('GET','/ai/models','Model versions and public evaluation metadata',null,async()=>{const result=await ai('/models');if(!Array.isArray(result.data))fail(502,'Invalid model catalog response.');return {data:result.data.map((m:any)=>({version:m.version,component:m.component,active:m.active,created_at:m.created_at,metadata:{status:m.metadata?.status,data_source:m.metadata?.data_source,calibrated:m.metadata?.calibrated,promotion_eligible:m.metadata?.promotion_eligible}}))};});
  route('GET','/admin/ai/metrics','Aggregate network prediction and verified outcome counts',null,async()=>({predictionCounts:await db.prediction.groupBy({by:['component','modelVersionId'],_count:true}),verifiedOutcomes:await db.referralOutcome.count({where:{verifiedAt:{not:null}}}),evaluation:await intelligenceMetrics()}),'system');
}
