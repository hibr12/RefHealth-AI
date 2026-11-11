import {useEffect,useRef,useState,type FormEvent} from 'react';
import {useInfiniteQuery,useQueryClient,type InfiniteData} from '@tanstack/react-query';
import {useSearchParams} from 'react-router-dom';
import axios from 'axios';
import {Plus,MessageSquare,ImagePlus,FileAudio,Mic,Square,Send,Volume2,X} from 'lucide-react';
import {api,get,errorMessage} from './api';
import {Heading,Status} from './ui';
import {AUDIO_ACCEPT,useAssistantMedia,useAssistantSpeech} from './assistant-media';
import './assistant.css';

type Thread={id:string;title:string;version:number;updatedAt:string};
type Turn={id:string;threadId:string;sequence:number;question:string;answer:string;sources:any[];createdAt:string;attachmentKind?:'image'|'audio'|null};
type ThreadList={threads:Thread[];nextCursor:string|null};
type ThreadPage={thread:Thread;conversations:Turn[];nextBefore:number|null};
type Saved={thread:Thread;conversation:Turn};

export function Assistant(){
  const [params,setParams]=useSearchParams(),cache=useQueryClient(),[locked,setLocked]=useState(false);
  const selected=params.get('chat'),fresh=params.get('new')==='1',selection=useRef(selected);selection.current=selected;
  const list=useInfiniteQuery({queryKey:['/assistant/threads'],initialPageParam:null as string|null,
    queryFn:({pageParam})=>get('/assistant/threads'+(pageParam?'?cursor='+encodeURIComponent(pageParam):'')) as Promise<ThreadList>,
    getNextPageParam:page=>page.nextCursor??undefined});
  const threads=[...new Map((list.data?.pages.flatMap(p=>p.threads)||[]).map(t=>[t.id,t])).values()];
  const detail=useInfiniteQuery({queryKey:['/assistant/threads',selected],enabled:!!selected,staleTime:15000,initialPageParam:null as number|null,
    queryFn:({pageParam})=>get(`/assistant/threads/${selected}`+(pageParam?'?before='+pageParam:'')) as Promise<ThreadPage>,
    getNextPageParam:page=>page.nextBefore??undefined});
  useEffect(()=>{if(!selected&&!fresh&&threads[0])setParams({chat:threads[0].id},{replace:true});},[selected,fresh,threads[0]?.id,setParams]);
  const thread=detail.data?.pages[0]?.thread;
  const turns=[...new Map((selected?detail.data?.pages.flatMap(p=>p.conversations)||[]:[]).map(t=>[t.id,t])).values()].sort((a,b)=>a.sequence-b.sequence);
  function saved(result:Saved,original:string|null){
    cache.setQueryData<InfiniteData<ThreadPage>>(['/assistant/threads',result.thread.id],old=>old?{...old,pages:old.pages.map((p,i)=>({...p,thread:result.thread,conversations:i===0?[...p.conversations.filter(t=>t.id!==result.conversation.id),result.conversation]:p.conversations}))}:{pages:[{thread:result.thread,conversations:[result.conversation],nextBefore:null}],pageParams:[null]});
    cache.setQueryData<InfiniteData<ThreadList>>(['/assistant/threads'],old=>old?{...old,pages:old.pages.map((p,i)=>({...p,threads:[...(i===0?[result.thread]:[]),...p.threads.filter(t=>t.id!==result.thread.id)]}))}:{pages:[{threads:[result.thread],nextCursor:null}],pageParams:[null]});
    if(selection.current===original)setParams({chat:result.thread.id},{replace:true});
  }
  const loading=selected?detail.isPending:!fresh&&list.isPending;
  return <>
    <Heading title="RefHealth AI Assistant" sub="Ask about your hospital, referrals, services, permissions and AI status using current authorized records."/>
    <p className="notice chat-privacy">Chats are saved privately to your account and hospital. Each chat has its own context. Answers use authorized records; missing or stale information should be stated. Messages and attachments are processed by configured AI providers. Voice transcripts are saved, but raw images and recordings are not retained. Do not share patient names, IDs, faces or clinical images.</p>
    <div className="assistant-layout">
      <aside className="panel chat-history" aria-label="Saved chats">
        <button className="chat-new" type="button" disabled={locked} onClick={()=>setParams({new:'1'})}><Plus size={17}/> New chat</button>
        <h2>Chat history</h2><p className="chat-history-note">Most recent first</p>
        <Status query={list}/>
        {!list.isPending&&!list.error&&!threads.length&&<p className="chat-history-empty">Your saved chats will appear here.</p>}
        <nav aria-label="Chat history">{threads.map(item=><button type="button" key={item.id} className={`chat-history-item${item.id===selected?' selected':''}`} aria-current={item.id===selected?'page':undefined} disabled={locked} onClick={()=>setParams({chat:item.id})}>
          <MessageSquare size={15}/><span><strong>{item.title}</strong><small>{new Date(item.updatedAt).toLocaleDateString()} · {item.version} {item.version===1?'reply':'replies'}</small></span>
        </button>)}</nav>
        {list.hasNextPage&&<button className="secondary" type="button" disabled={list.isFetchingNextPage} onClick={()=>void list.fetchNextPage()}>{list.isFetchingNextPage?'Loading...':'Load more chats'}</button>}
        {list.error&&<button className="secondary" type="button" onClick={()=>void list.refetch()}>Retry history</button>}
      </aside>
      <ChatPane key={selected||'new'} threadId={selected} thread={thread} turns={turns} loading={loading} loadError={selected?detail.error:list.error}
        setLocked={setLocked} onSaved={saved} onConflict={()=>{void detail.refetch();void list.refetch();}}
        hasEarlier={!!detail.hasNextPage} fetchingEarlier={detail.isFetchingNextPage} loadEarlier={()=>void detail.fetchNextPage()} retry={()=>void(selected?detail.refetch():list.refetch())}/>
    </div>
  </>;
}

type PaneProps={threadId:string|null;thread?:Thread;turns:Turn[];loading:boolean;loadError:unknown;setLocked:(value:boolean)=>void;onSaved:(result:Saved,original:string|null)=>void;onConflict:()=>void;hasEarlier:boolean;fetchingEarlier:boolean;loadEarlier:()=>void;retry:()=>void};
function ChatPane({threadId,thread,turns,loading,loadError,setLocked,onSaved,onConflict,hasEarlier,fetchingEarlier,loadEarlier,retry}:PaneProps){
  const [draft,setDraft]=useState(''),[referralId,setReferralId]=useState(''),[busy,setBusy]=useState(false),[error,setError]=useState('');
  const {attachment,phase,chooseImage,chooseAudio,clearAttachment,toggleRecording}=useAssistantMedia(setError);
  const {speaking,speak}=useAssistantSpeech(setError);
  const recording=phase==='recording',mediaBusy=phase!=='idle',disabled=busy||mediaBusy||loading||!!loadError;
  const imageInput=useRef<HTMLInputElement>(null),audioInput=useRef<HTMLInputElement>(null),scroll=useRef<HTMLDivElement>(null);
  const pending=useRef<{signature:string;id:string}|null>(null),sending=useRef(false);
  useEffect(()=>{setLocked(busy||mediaBusy);return()=>setLocked(false);},[busy,mediaBusy,setLocked]);
  const latest=turns.at(-1)?.id;
  useEffect(()=>{scroll.current?.scrollTo({top:scroll.current.scrollHeight,behavior:'smooth'});},[latest,busy]);
  async function send(event:FormEvent){
    event.preventDefault();if(disabled||sending.current)return;
    const media=attachment,prompt=draft.trim()||(media?.kind==='audio'?'Please listen to this voice message and respond about RefHealth AI coordination.':media?.kind==='image'?'Please describe this image in the context of hospital coordination.':'');
    if(!prompt)return;
    sending.current=true;setBusy(true);setError('');
    const payload={question:prompt,...(threadId?{threadId,expectedVersion:thread?.version}:{}),...(referralId.trim()?{referralId:referralId.trim()}:{}),...(media?{attachment:{mime_type:media.mime_type,data:media.data}}:{})};
    const signature=JSON.stringify({...payload,expectedVersion:undefined});
    if(pending.current?.signature!==signature)pending.current={signature,id:crypto.randomUUID()};
    try{
      const response=await api.post('/assistant/chat',{...payload,clientRequestId:pending.current.id},{timeout:100000});
      onSaved(response.data,threadId);pending.current=null;setDraft('');setReferralId('');clearAttachment();
    }catch(e){
      setError(axios.isAxiosError(e)?e.response?.data?.error?.message||'The assistant could not complete this message. Your draft is ready to retry.':e instanceof Error?e.message:'The assistant could not complete this message.');
      if(axios.isAxiosError(e)&&e.response?.status===409)onConflict();
    }finally{sending.current=false;setBusy(false);}
  }
  return <section className="panel chat-panel" aria-label="Current chat">
    <header className="chat-thread-heading"><h2>{thread?.title||'New chat'}</h2><small>{thread?'Saved to your private history':'Start a separate conversation'}</small></header>
    <div className="chat-messages" ref={scroll} aria-live="polite">
      {loading&&<p role="status">Loading chat...</p>}
      {!!loadError&&<div><p className="error" role="alert">{errorMessage(loadError)}</p><button type="button" className="secondary" onClick={retry}>Retry chat</button></div>}
      {hasEarlier&&<button className="secondary chat-load-earlier" type="button" disabled={fetchingEarlier} onClick={loadEarlier}>{fetchingEarlier?'Loading...':'Load earlier messages'}</button>}
      {!turns.length&&!loading&&!loadError&&<div className="chat-welcome"><span className="assistant-symbol">✳</span><h2>How can I help with care coordination?</h2><p>Ask what is pending in your workspace, or what your role can do. Attach an operational image or a short voice message if helpful.</p></div>}
      {turns.map(turn=><div className="chat-turn" key={turn.id}>
        <article className="chat-message user"><div className="chat-bubble"><p>{turn.question}</p>{turn.attachmentKind&&<small className="chat-media-note">{turn.attachmentKind==='image'?'Image':'Voice recording'} sent; raw media is not retained</small>}</div></article>
        <article className="chat-message assistant"><div className="chat-bubble"><p>{turn.answer}</p>
          <button className="chat-speak" type="button" onClick={()=>speak(turn.answer,turn.sequence,turn.id)} aria-label={speaking===turn.sequence?'Stop reading aloud':'Read answer aloud'}>{speaking===turn.sequence?<Square size={15}/>:<Volume2 size={15}/>} {speaking===turn.sequence?'Stop':'Listen'}</button>
          {!!turn.sources?.length&&<details className="chat-sources"><summary>Sources ({turn.sources.length})</summary>{turn.sources.map(source=><p key={source.id}><strong>{source.source}</strong> · {source.category??'authorized source'}{source.stale?' · Review overdue':''}<br/>{source.content}</p>)}</details>}
        </div></article>
      </div>)}
      {busy&&<div className="chat-working" role="status">RefHealth AI Assistant is preparing a response...</div>}
    </div>
    <form className="chat-composer" onSubmit={send}>
      {error&&<p className="error" role="alert">{error}</p>}
      {attachment&&<div className="chat-attachment-preview">{attachment.kind==='image'?<img src={attachment.preview} alt="Selected image preview"/>:<audio controls src={attachment.preview}/>}<span>{attachment.name} · sent only with your next message</span><button type="button" className="icon-button" onClick={clearAttachment} disabled={disabled} aria-label="Remove attachment"><X size={16}/></button></div>}
      <label className="chat-referral">Referral ID (optional)<input value={referralId} onChange={event=>setReferralId(event.target.value)} placeholder="Discuss saved AI results" maxLength={200} disabled={disabled}/></label>
      <textarea aria-label="Message RefHealth AI Assistant" placeholder="Type a message... (Shift+Enter for a new line)" value={draft} onChange={event=>setDraft(event.target.value)} onKeyDown={event=>{if(event.key==='Enter'&&!event.shiftKey){event.preventDefault();event.currentTarget.form?.requestSubmit();}}} maxLength={2000} rows={2} disabled={disabled}/>
      <div className="chat-controls">
        <input ref={imageInput} type="file" accept="image/jpeg,image/png,image/webp" hidden onChange={event=>{void chooseImage(event.target.files?.[0]);event.target.value='';}}/>
        <input ref={audioInput} type="file" accept={AUDIO_ACCEPT} hidden onChange={event=>{void chooseAudio(event.target.files?.[0]);event.target.value='';}}/>
        <button className="secondary chat-icon-button" type="button" onClick={()=>imageInput.current?.click()} disabled={disabled} aria-label="Attach image" title="Attach image"><ImagePlus size={18}/></button>
        <button className="secondary chat-icon-button" type="button" onClick={()=>audioInput.current?.click()} disabled={disabled} aria-label="Attach audio" title="Attach audio"><FileAudio size={18}/></button>
        <button className={`secondary chat-icon-button ${recording?'recording':''}`} type="button" onClick={()=>void toggleRecording()} disabled={busy||loading||!!loadError||(mediaBusy&&!recording)} aria-label={recording?'Stop recording':'Record voice message'}>{recording?<Square size={17}/>:<Mic size={18}/>}</button>
        <span className="chat-hint">{recording?'Recording... click stop':phase==='starting'?'Waiting for microphone...':phase==='preparing'?'Preparing attachment...':'Text, image or voice · 4 MB max'}</span>
        <button className="chat-send" type="submit" disabled={disabled||(!draft.trim()&&!attachment)}><Send size={17}/> {busy?'Sending...':'Send'}</button>
      </div>
    </form>
  </section>;
}
