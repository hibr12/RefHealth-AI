import { z } from 'zod';
import { randomUUID } from 'node:crypto';
import { type Context, db, audit } from './app.js';
import { config } from './config.js';
import { hashPassword, verifyPassword, token, digest, fail } from './security.js';
import * as c from './contracts.js';
export function authRoutes({app,route}:Context) {
  const options={httpOnly:true,secure:config.NODE_ENV==='production',sameSite:'strict' as const,path:'/',maxAge:7*86400};
  const dummy=hashPassword('unavailable-account-password');
  async function credentials(user:any,hospitalId:string|null,reply:any,sessionId?:string) {
    const id=randomUUID();
    const refresh=app.jwt.sign({sub:user.id,sid:id,kind:'refresh',jti:token()},{expiresIn:'7d'});
    const session=await db.session.create({data:{id,userId:user.id,tokenHash:digest(refresh),expiresAt:new Date(Date.now()+7*86400000)}});
    reply.setCookie('refresh',refresh,options);
    return {accessToken:app.jwt.sign({sub:user.id,sid:session.id,hid:hospitalId,kind:'access'},{expiresIn:'15m'}),user:{id:user.id,email:user.email,name:user.name,role:user.role,hospitalId,permissions:user.memberships?.find((m:any)=>m.hospitalId===hospitalId)?.permissions??[]}};
  }
  route('POST','/auth/login','Sign in',c.login,async(_r,b,reply)=>{
    const user=await db.user.findUnique({where:{email:b.email},include:{memberships:{where:{active:true},include:{hospital:true}}}});
    const valid=await verifyPassword(b.password,user?.passwordHash??await dummy);
    if(!valid||!user?.active)fail(401,'Invalid credentials or inactive account.');
    const membership=user!.memberships.find(m=>m.hospital.status==='APPROVED');
    if(user!.role!=='SYSTEM_ADMIN'&&!membership)fail(403,'Hospital approval or activation is pending.');
    await db.auditLog.create({data:{actorId:user!.id,action:'LOGIN'}});
    return credentials(user,membership?.hospitalId??null,reply);
  },'public');
  route('POST','/auth/refresh','Rotate refresh token',null,async(r,_b,reply)=>{
    const value=r.cookies.refresh;if(!value)fail(401,'Session expired.');
    try {const claims=app.jwt.verify<{kind:string}>(value!);if(claims.kind!=='refresh')fail(401,'Refresh token required.');}catch{fail(401,'Session expired.');}
    const session=await db.session.findUnique({where:{tokenHash:digest(value!)},include:{user:{include:{memberships:{include:{hospital:true}}}}}});
    if(!session||session.revokedAt||session.expiresAt<new Date()||!session.user.active)fail(401,'Session expired.');
    const membership=session!.user.memberships.find(m=>m.active&&m.hospital.status==='APPROVED');
    if(session!.user.role!=='SYSTEM_ADMIN'&&!membership)fail(403,'Hospital access is inactive.');
    const used=await db.session.updateMany({where:{id:session!.id,revokedAt:null},data:{revokedAt:new Date()}});
    if(used.count!==1)fail(401,'Refresh token was already used.');
    return credentials(session!.user,membership?.hospitalId??null,reply);
  },'public');
  route('POST','/auth/logout','Revoke session',null,async(r,_b,reply)=>{await db.session.update({where:{id:r.actor.sessionId},data:{revokedAt:new Date()}});reply.clearCookie('refresh',options);return {success:true};},'any');
  route('GET','/auth/me','Current identity',null,async r=>({user:r.actor}),'any');
  route('POST','/auth/reset-request','Request password recovery',z.object({email:c.email}),async(_r,b)=>{
    // A platform operator issues a single-use recovery token after identity verification.
    const user=await db.user.findUnique({where:{email:b.email}});
    if(user)await db.auditLog.create({data:{actorId:user.id,action:'PASSWORD_RESET_REQUESTED',resourceId:user.id}});
    return {message:'If the account exists, a recovery request has been recorded. Contact your platform administrator for a secure recovery link.'};
  },'public');
  route('POST','/auth/complete','Activate account or reset password',z.object({token:c.text,password:c.password}),async(_r,b)=>{
    const entry=await db.accountToken.findUnique({where:{tokenHash:digest(b.token)}});
    if(!entry||entry.usedAt||entry.expiresAt<new Date())fail(400,'Invalid or expired account token.');
    const passwordHash=await hashPassword(b.password);
    await db.$transaction(async tx=>{
      const used=await tx.accountToken.updateMany({where:{id:entry!.id,usedAt:null},data:{usedAt:new Date()}});
      if(used.count!==1)fail(409,'Account token already used.');
      await tx.user.update({where:{id:entry!.userId},data:{passwordHash,active:true}});
      await tx.session.updateMany({where:{userId:entry!.userId},data:{revokedAt:new Date()}});
      await tx.auditLog.create({data:{actorId:entry!.userId,action:'ACCOUNT_TOKEN_REDEEMED'}});
    });return {success:true};
  },'public');
  route('POST','/admin/users/:id/token','Issue single-use activation or recovery token',z.object({purpose:z.enum(['ACTIVATION','RESET'])}),async(r,b)=>{
    const id=(r.params as any).id;const value=token();
    await db.$transaction(async tx=>{await tx.accountToken.updateMany({where:{userId:id,usedAt:null},data:{usedAt:new Date()}});await tx.accountToken.create({data:{userId:id,tokenHash:digest(value),purpose:b.purpose,expiresAt:new Date(Date.now()+3600000)}});await audit(r.actor,'ACCOUNT_TOKEN_ISSUED',id,tx);});
    return {token:value,expiresInSeconds:3600};
  },'system');
}
