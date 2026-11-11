import Fastify, { type FastifyInstance, type FastifyReply, type FastifyRequest } from 'fastify';
import cookie from '@fastify/cookie';
import cors from '@fastify/cors';
import helmet from '@fastify/helmet';
import jwt from '@fastify/jwt';
import rateLimit from '@fastify/rate-limit';
import swagger from '@fastify/swagger';
import swaggerUI from '@fastify/swagger-ui';
import { PrismaClient, Prisma } from '../generated/prisma/index.js';
import { z, ZodError } from 'zod';
import { zodToJsonSchema } from 'zod-to-json-schema';
import { config, trustedOrigins } from './config.js';
import { fail, ApiError } from './security.js';
import { authRoutes } from './auth.js';
import { hospitalRoutes } from './hospitals.js';
import { referralRoutes } from './referrals.js';
import { intelligenceRoutes } from './intelligence.js';
import { incomingQueueRoutes } from './incoming-queue.js';
export const db = new PrismaClient();
export type Actor = {id:string;name:string;email:string;role:string;hospitalId:string|null;permissions:string[];sessionId:string};
declare module 'fastify' { interface FastifyRequest { actor:Actor } }
export type Context = {app:FastifyInstance; route:ReturnType<typeof router>};
export const page = (q:any) => {const v=z.object({page:z.coerce.number().int().min(1).default(1),limit:z.coerce.number().int().min(1).max(100).default(30)}).parse(q);return {skip:(v.page-1)*v.limit,take:v.limit};};
export const own = (r:FastifyRequest) => r.actor.hospitalId || fail(403,'Hospital workspace required.');
export const hospitalAdmin = (r:FastifyRequest) => {own(r);if(r.actor.role!=='HOSPITAL_ADMIN') fail(403,'Hospital administrator required.');};
export async function audit(actor:Actor|undefined,action:string,resourceId?:string,client:any=db) {await client.auditLog.create({data:{actorId:actor?.id,hospitalId:actor?.hospitalId,action,resourceId}});}
function router(app:FastifyInstance) {
  return (method:'GET'|'POST'|'PATCH',url:string,summary:string,body:z.ZodTypeAny|null,handler:(r:FastifyRequest,b:any,reply:FastifyReply)=>Promise<any>,access:'public'|'system'|'hospital'|'any'='hospital',options?:{bodyLimit?:number}) => {
    const names=[...url.matchAll(/:([A-Za-z]+)/g)].map(m=>m[1]);
    app.route({method,url,...(options?.bodyLimit?{bodyLimit:options.bodyLimit}:{}),schema:{tags:[url.split('/')[1]],summary,security:access==='public'?[]:[{bearerAuth:[]}],
      ...(names.length?{params:{type:'object',required:names,properties:Object.fromEntries(names.map(name=>[name,{type:'string',minLength:1,maxLength:200}]))}}:{}),
      ...(body?{body:zodToJsonSchema(body,{$refStrategy:'none'})}:{}),
      response:{200:{description:'Successful JSON result',type:'object',additionalProperties:true},400:{description:'Invalid input'},401:{description:'Authentication required'},403:{description:'Not authorized'},409:{description:'Conflict'},503:{description:'Dependency unavailable'}}},
      preHandler:async r=>{
        if(access==='public')return;
        try {await r.jwtVerify();}catch {fail(401,'Sign in to continue.');}
        const claims=r.user as {sub:string;sid:string;hid:string|null;kind:string};
        if(claims.kind!=='access')fail(401,'Access token required.');
        const session=await db.session.findFirst({where:{id:claims.sid,userId:claims.sub,revokedAt:null,expiresAt:{gt:new Date()}},include:{user:{include:{memberships:{include:{hospital:true}}}}}});
        if(!session?.user.active)fail(401,'Session is inactive.');
        const user=session!.user;
        const membership=user.memberships.find(m=>m.hospitalId===claims.hid&&m.active&&m.hospital.status==='APPROVED');
        if(user.role!=='SYSTEM_ADMIN'&&!membership)fail(403,'Hospital access is not active.');
        r.actor={id:user.id,name:user.name,email:user.email,role:user.role,hospitalId:membership?.hospitalId??null,permissions:membership?.permissions??[],sessionId:session!.id};
        if(access==='system'&&user.role!=='SYSTEM_ADMIN')fail(403,'Platform administrator required.');
        if(access==='hospital')own(r);
      }, handler:async(r,reply)=>handler(r,body?body.parse(r.body):undefined,reply)});
  };
}
export async function buildApp() {
  const app=Fastify({ajv:{customOptions:{removeAdditional:false}},logger:config.NODE_ENV==='test'?false:{redact:['req.headers.authorization','req.headers.cookie','res.headers["set-cookie"]']},bodyLimit:1024*1024});
  await app.register(cookie);
  await app.register(cors,{origin:trustedOrigins,credentials:true});
  await app.register(helmet);
  await app.register(jwt,{secret:config.JWT_SECRET});
  await app.register(rateLimit,{max:150,timeWindow:'1 minute'});
  await app.register(swagger,{openapi:{info:{title:'RefHealth AI API',version:'1.0.0'},components:{securitySchemes:{bearerAuth:{type:'http',scheme:'bearer',bearerFormat:'JWT'}}}}});
  await app.register(swaggerUI,{routePrefix:'/docs'});
  app.addHook('onRequest',async(r,reply)=>{
    reply.header('Cache-Control','no-store');
    if(!['GET','HEAD','OPTIONS'].includes(r.method)&&r.headers.origin&&!trustedOrigins.includes(r.headers.origin))fail(403,'Untrusted request origin.');
  });
  app.setErrorHandler((error,_r,reply)=>{
    if(error instanceof ZodError)return reply.code(400).send({error:{message:'Invalid input.',details:error.issues.map(i=>({field:i.path.join('.'),message:i.message}))}});
    if(error instanceof Prisma.PrismaClientKnownRequestError){
      const status=error.code==='P2002'||error.code==='P2034'?409:error.code==='P2025'?404:400;
      return reply.code(status).send({error:{message:status===409?'This record already exists or changed concurrently. Please reload.':'Record operation could not be completed.'}});
    }
    const status=error instanceof ApiError?error.statusCode:((error as any).statusCode||500);
    if(status>=500)app.log.error({status,requestId:_r.id,errorType:error instanceof Error?error.name:'Unknown'},'Request failed');
    return reply.code(status).send({error:{message:status===500?'Unexpected server error.':error instanceof Error?error.message:'Request failed.'}});
  });
  const context={app,route:router(app)};
  context.route('GET','/health','Database readiness',null,async()=>{await db.$queryRaw`SELECT 1`;return {status:'ok'};},'public');
  authRoutes(context);hospitalRoutes(context);referralRoutes(context);incomingQueueRoutes(context);intelligenceRoutes(context);
  return app;
}
