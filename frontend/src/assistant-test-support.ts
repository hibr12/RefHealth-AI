import {vi} from 'vitest';
import {get} from './api';
let sequence=0;
export function resetChatFixtures(){sequence=0;vi.mocked(get).mockResolvedValue({threads:[],nextCursor:null});}
export function savedReply(answer:string,question='User message'){
  sequence++;
  return {conversation:{id:'reply-'+sequence,threadId:'thread-test',sequence,question,answer,sources:[],createdAt:new Date().toISOString()},thread:{id:'thread-test',title:'Test chat',version:sequence,updatedAt:new Date().toISOString()}};
}
export function savedHistory(rows:any[]){
  const thread={id:'thread-test',title:'Test chat',version:rows.length,updatedAt:new Date().toISOString()};
  vi.mocked(get).mockImplementation(async path=>path==='/assistant/threads'?{threads:[thread],nextCursor:null}:{thread,conversations:rows.map((row,i)=>({...row,threadId:thread.id,sequence:i+1,createdAt:row.createdAt||new Date().toISOString()})),nextBefore:null});
}
