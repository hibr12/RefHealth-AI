import {z} from 'zod';

export const priority = z.enum(['CRITICAL','HIGH','MEDIUM','LOW']);
export const observationField = z.string().regex(/^(urgency|requiredService|requiredSpecialty|symptoms|riskIndicators|vitals\.[a-zA-Z][a-zA-Z0-9_]{0,39})$/);
export const clinicalObservations = z.object({
  symptoms:z.array(z.string().trim().min(1).max(200)).max(50).default([]),
  riskIndicators:z.array(z.string().trim().min(1).max(200)).max(50).default([]),
  vitals:z.record(z.string().regex(/^[a-zA-Z][a-zA-Z0-9_]{0,39}$/),z.object({value:z.number().finite(),unit:z.string().trim().min(1).max(40)}).strict()).refine(v=>Object.keys(v).length<=30).default({}),
}).strict();
const condition=z.object({field:observationField,operator:z.enum(['equals','contains','gte','lte']),value:z.union([z.string().min(1).max(200),z.number().finite()]),unit:z.string().min(1).max(40).optional()}).strict().superRefine((c,ctx)=>{
  const vital=c.field.startsWith('vitals.');
  if(vital&&(!c.unit||typeof c.value!=='number'||c.operator==='contains'))ctx.addIssue({code:'custom',message:'Vital conditions require a numeric value, exact unit and numeric comparison.'});
  if(!vital&&(typeof c.value!=='string'||!['equals','contains'].includes(c.operator)))ctx.addIssue({code:'custom',message:'Categorical conditions require a string comparison.'});
  if(['symptoms','riskIndicators'].includes(c.field)!==(c.operator==='contains'))ctx.addIssue({code:'custom',message:'Use contains only for structured symptoms or risk indicators.'});
});
export const protocol=z.object({
  name:z.string().trim().min(3).max(200),version:z.string().trim().min(1).max(100),
  reference:z.string().trim().min(5).max(1000),approvedBy:z.string().trim().min(3).max(200),
  clinicalValidationReference:z.string().trim().min(5).max(1000),
  approvedAt:z.string().datetime().refine(v=>new Date(v).getTime()<=Date.now(),'Approval cannot be in the future.'),
  approvalAttested:z.literal(true),requiredFields:z.array(observationField).min(1).max(40),
  rules:z.array(z.object({id:z.string().min(1).max(80),priority,explanation:z.string().trim().min(5).max(1000),conditions:z.array(condition).min(1).max(20)}).strict()).min(1).max(100),
}).strict().refine(p=>new Set(p.rules.map(r=>r.id)).size===p.rules.length,'Rule IDs must be unique.');
export const deadlines=z.object(Object.fromEntries(['CRITICAL','HIGH','MEDIUM','LOW','REVIEW_REQUIRED'].map(p=>[p,z.object({minutes:z.number().int().min(1).max(525600),warningMinutes:z.number().int().min(0).max(525600)}).strict().refine(d=>d.warningMinutes<=d.minutes,'Warning lead time cannot exceed the deadline.').optional()]))).strict();
export const queuePolicy=z.object({
  version:z.number().int().nonnegative(),
  timezone:z.string().max(100).refine(v=>{try{new Intl.DateTimeFormat('en',{timeZone:v});return true;}catch{return false;}},'Use an IANA timezone.'),
  deadlines,emergencyProcedure:z.string().trim().max(4000),protocol:protocol.nullable(),
}).strict();
export const priorityReview=z.object({priority,reason:z.string().trim().min(5).max(2000),version:z.number().int().nonnegative()}).strict();
export const versionBody=z.object({version:z.number().int().nonnegative()}).strict();
export const queueQuery=z.object({
  page:z.coerce.number().int().min(1).max(100000).default(1),limit:z.coerce.number().int().min(1).max(100).default(30),
  priority:z.enum(['CRITICAL','HIGH','MEDIUM','LOW','REVIEW_REQUIRED']).optional(),
  originId:z.string().max(200).optional(),service:z.string().max(200).optional(),
  status:z.enum(['SUBMITTED','ACCEPTED','IN_PROGRESS','COMPLETED','REJECTED','CANCELLED','ALL']).optional(),
  acknowledged:z.enum(['yes','no']).optional(),overdue:z.enum(['true']).optional(),review:z.enum(['true']).optional(),
  arrivedFrom:z.string().datetime({offset:true}).optional(),arrivedTo:z.string().datetime({offset:true}).optional(),
  minWaitingMinutes:z.coerce.number().min(0).max(5256000).optional(),
  sort:z.enum(['priority','arrival','waiting']).default('priority'),
}).strict().refine(q=>!q.arrivedFrom||!q.arrivedTo||new Date(q.arrivedFrom)<=new Date(q.arrivedTo),'Arrival range is reversed.');
