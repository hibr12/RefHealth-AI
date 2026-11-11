import {z} from 'zod';
import {db,own,type Actor,type Context} from './app.js';
import {fail} from './security.js';

export const threadScope=(actor:Actor)=>({hospitalId:actor.hospitalId!,userId:actor.id});
export function publicConversation<T extends {requestDigest?:unknown;clientRequestId?:unknown}>(row:T){const {requestDigest,clientRequestId,...visible}=row;return visible;}
export async function ownedThread(actor:Actor,id:string,client:Pick<typeof db,'chatThread'>=db){
  const thread=await client.chatThread.findFirst({where:{id,...threadScope(actor)}});
  if(!thread)return fail(404,'Chat not found.');
  return thread;
}
export function assistantThreadRoutes({route}:Pick<Context,'route'>){
  route('GET','/assistant/threads','Your saved chats, most recently active first',null,async r=>{
    own(r);
    const query=z.object({limit:z.coerce.number().int().min(1).max(50).default(30),cursor:z.string().max(400).optional()}).parse(r.query);
    let cursor:{at:string;id:string}|undefined;
    if(query.cursor){try{cursor=z.object({at:z.string().datetime(),id:z.string().uuid()}).parse(JSON.parse(Buffer.from(query.cursor,'base64url').toString()));}catch{return fail(400,'Invalid chat history cursor.');}}
    const rows=await db.chatThread.findMany({where:{...threadScope(r.actor),...(cursor?{OR:[{updatedAt:{lt:new Date(cursor.at)}},{updatedAt:new Date(cursor.at),id:{lt:cursor.id}}]}:{})},orderBy:[{updatedAt:'desc'},{id:'desc'}],take:query.limit+1});
    const threads=rows.slice(0,query.limit),last=threads.at(-1);
    return {threads,nextCursor:rows.length>query.limit&&last?Buffer.from(JSON.stringify({at:last.updatedAt.toISOString(),id:last.id})).toString('base64url'):null};
  });
  route('GET','/assistant/threads/:id','Read your chat in message order',null,async r=>{
    own(r);
    const query=z.object({before:z.coerce.number().int().positive().optional(),limit:z.coerce.number().int().min(1).max(100).default(40)}).parse(r.query);
    return db.$transaction(async tx=>{
    const thread=await ownedThread(r.actor,(r.params as any).id,tx);
    const rows=await tx.conversation.findMany({where:{threadId:thread.id,...threadScope(r.actor),...(query.before?{sequence:{lt:query.before}}:{})},orderBy:{sequence:'desc'},take:query.limit+1});
    const conversations=rows.slice(0,query.limit).reverse();
    return {thread,conversations:conversations.map(publicConversation),nextBefore:rows.length>query.limit?conversations[0].sequence:null};
    },{isolationLevel:'RepeatableRead'});
  });
}
