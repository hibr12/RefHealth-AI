import https from 'node:https';
import dns from 'node:dns/promises';
import {db} from './app.js';
export function publicIPv4(address:string){
  if(!/^\d+\.\d+\.\d+\.\d+$/.test(address))return false;
  const [a,b,c,d]=address.split('.').map(Number);
  if([a,b,c,d].some(x=>x>255))return false;
  return !(a===0||a===10||a===127||a>=224||(a===169&&b===254)||(a===172&&b>=16&&b<=31)||(a===192&&b===168)||(a===100&&b>=64&&b<=127)||(a===198&&(b===18||b===19))||(a===192&&b===0)||(a===198&&b===51)||(a===203&&b===0&&c===113));
}
export async function collectPublicText(raw:string):Promise<string>{
  const url=new URL(raw);if(url.protocol!=='https:'||url.username||url.password||(url.port&&url.port!=='443'))throw new Error('Only public HTTPS sources on port 443 are supported.');
  const addresses=await dns.resolve4(url.hostname);if(!addresses.length||addresses.some(x=>!publicIPv4(x)))throw new Error('Source must resolve only to public IPv4 addresses.');
  const body=await new Promise<string>((resolve,reject)=>{
    // Pin the DNS result for this connection to prevent DNS rebinding; never follow redirects.
    const req=https.get(url,{lookup:((_host:any,options:any,callback:any)=>options.all?callback(null,addresses.map(address=>({address,family:4}))):callback(null,addresses[0],4)) as any,headers:{'User-Agent':'RefHealth AI AuthorizedSourceCollector/1.0','Accept':'text/html,text/plain,application/rss+xml,application/atom+xml,application/xml'}},res=>{
      if(res.statusCode!==200){res.resume();reject(new Error('Source did not return HTTP 200. Redirects require registering the final URL.'));return;}
      if(!/text\/|application\/(rss\+xml|atom\+xml|xml)/i.test(res.headers['content-type']||'')){res.resume();reject(new Error('Unsupported source content type.'));return;}
      const chunks:Buffer[]=[];let size=0;res.on('data',chunk=>{size+=chunk.length;if(size>1024*1024){req.destroy(new Error('Source exceeds 1 MB limit.'));return;}chunks.push(chunk);});res.on('end',()=>resolve(Buffer.concat(chunks).toString('utf8')));res.on('error',reject);
    });req.setTimeout(10000,()=>req.destroy(new Error('Source collection timed out.')));req.on('error',reject);
  });
  const text=body.replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi,' ').replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi,' ').replace(/<[^>]*>/g,' ').replace(/\s+/g,' ').trim();
  if(text.length<3)throw new Error('No readable source content.');return text.slice(0,4000);
}
export async function processSourceJob(fetcher=collectPublicText){
  const job=await db.sourceJob.findFirst({where:{status:'PENDING'},orderBy:{createdAt:'asc'},include:{source:true}});if(!job)return;
  const claimed=await db.sourceJob.updateMany({where:{id:job.id,status:'PENDING'},data:{status:'RUNNING'}});if(claimed.count!==1)return;
  try{
    if(!['WEBSITE','FEED'].includes(job.source.kind)||job.source.permissionStatus!=='PERMITTED_PUBLIC_ACCESS')throw new Error('Source collection is not authorized.');
    const content=await fetcher(job.source.url);
    await db.$transaction(async tx=>{await tx.knowledgeRecord.create({data:{hospitalId:job.hospitalId,category:'external',content,source:job.source.url,createdBy:job.actorId,visibility:'PRIVATE'}});await tx.sourceJob.update({where:{id:job.id},data:{status:'COMPLETED'}});await tx.externalSource.update({where:{id:job.sourceId},data:{status:'FETCHED_PENDING_REVIEW'}});await tx.auditLog.create({data:{actorId:job.actorId,hospitalId:job.hospitalId,action:'SOURCE_COLLECTED_FOR_REVIEW',resourceId:job.sourceId}});});
  }catch(e){await db.$transaction([db.sourceJob.update({where:{id:job.id},data:{status:'FAILED',error:e instanceof Error?e.message:'Source collection failed.'}}),db.externalSource.update({where:{id:job.sourceId},data:{status:'COLLECTION_FAILED'}})]);}
}
