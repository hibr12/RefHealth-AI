import {useEffect,useRef,useState} from 'react';
import {api,errorMessage} from './api';

export type AssistantAttachment={kind:'image'|'audio';mime_type:string;data:string;preview:string;name:string};
export const MAX_MEDIA_BYTES=4*1024*1024;
export const AUDIO_ACCEPT='.wav,.mp3,.mp4,.m4a,.mpeg,.mpga,.ogg,.flac,.webm,.opus';
const audioTypes:Record<string,string>={wav:'audio/wav',mp3:'audio/mpeg',mp4:'audio/mp4',m4a:'audio/mp4',mpeg:'audio/mpeg',mpga:'audio/mpeg',ogg:'audio/ogg',flac:'audio/flac',webm:'audio/webm',opus:'audio/ogg'};
const audioAliases:Record<string,string>={'audio/x-wav':'audio/wav','audio/wave':'audio/wav','audio/x-m4a':'audio/mp4','audio/m4a':'audio/mp4','audio/mp3':'audio/mpeg','audio/opus':'audio/ogg','audio/x-flac':'audio/flac','video/mp4':'audio/mp4'};
function dataUrl(blob:Blob){return new Promise<string>((resolve,reject)=>{const reader=new FileReader();reader.onerror=()=>reject(new Error('Could not read this file.'));reader.onload=()=>resolve(String(reader.result));reader.readAsDataURL(blob);});}
export async function prepareAudio(file:File):Promise<AssistantAttachment>{
  const supplied=file.type.split(';')[0].toLowerCase();
  const mime=audioAliases[supplied]||supplied||audioTypes[file.name.split('.').pop()?.toLowerCase()||''];
  if(!Object.values(audioTypes).includes(mime))throw new Error('Choose a WAV, MP3, M4A, MP4, OGG, FLAC, or WebM audio file.');
  if(!file.size)throw new Error('No audio was captured. Record a message and try again.');
  if(file.size>MAX_MEDIA_BYTES)throw new Error('The audio file must be smaller than 4 MB.');
  const blob=new Blob([file],{type:mime}),url=await dataUrl(blob);
  return {kind:'audio',mime_type:mime,data:url.split(',')[1],preview:URL.createObjectURL(blob),name:file.name};
}
export async function prepareImage(file:File):Promise<AssistantAttachment>{
  if(!['image/jpeg','image/png','image/webp'].includes(file.type))throw new Error('Choose a JPEG, PNG, or WebP image.');
  if(!file.size||file.size>20*1024*1024)throw new Error('Choose an image smaller than 20 MB.');
  const bitmap=await createImageBitmap(file);
  try{
    if(bitmap.width*bitmap.height>36_000_000)throw new Error('Choose an image with fewer than 36 million pixels.');
    const scale=Math.min(1,1280/Math.max(bitmap.width,bitmap.height)),canvas=document.createElement('canvas');
    canvas.width=Math.max(1,Math.round(bitmap.width*scale));canvas.height=Math.max(1,Math.round(bitmap.height*scale));
    const context=canvas.getContext('2d');if(!context)throw new Error('This browser cannot prepare the image.');
    context.fillStyle='white';context.fillRect(0,0,canvas.width,canvas.height);context.drawImage(bitmap,0,0,canvas.width,canvas.height);
    const blob=await new Promise<Blob|null>(resolve=>canvas.toBlob(resolve,'image/jpeg',0.78));
    if(!blob||blob.size>MAX_MEDIA_BYTES)throw new Error('Could not compress this image below 4 MB.');
    const url=await dataUrl(blob);
    return {kind:'image',mime_type:'image/jpeg',data:url.split(',')[1],preview:url,name:file.name};
  }finally{bitmap.close();}
}

export function useAssistantMedia(onError:(message:string)=>void){
  const [attachment,setAttachment]=useState<AssistantAttachment|null>(null);
  const [phase,setPhase]=useState<'idle'|'starting'|'recording'|'preparing'>('idle');
  const current=useRef<AssistantAttachment|null>(null),generation=useRef(0),mounted=useRef(true);
  const recorder=useRef<MediaRecorder|null>(null),stream=useRef<MediaStream|null>(null),timer=useRef<number|null>(null);
  function releaseCapture(){
    if(timer.current!==null)window.clearTimeout(timer.current);timer.current=null;
    stream.current?.getTracks().forEach(track=>track.stop());stream.current=null;
  }
  function replace(next:AssistantAttachment|null){
    if(current.current?.preview.startsWith('blob:'))URL.revokeObjectURL(current.current.preview);
    current.current=next;setAttachment(next);
  }
  useEffect(()=>{mounted.current=true;return()=>{
    mounted.current=false;generation.current++;
    const active=recorder.current;
    if(active){active.onstop=null;active.ondataavailable=null;active.onerror=null;if(active.state!=='inactive')active.stop();}
    releaseCapture();
    if(current.current?.preview.startsWith('blob:'))URL.revokeObjectURL(current.current.preview);
  };},[]);
  async function choose(file:File|undefined,kind:'image'|'audio'){
    if(!file)return;
    const id=++generation.current;onError('');setPhase('preparing');
    try{
      const next=await (kind==='image'?prepareImage(file):prepareAudio(file));
      if(!mounted.current||id!==generation.current){if(next.preview.startsWith('blob:'))URL.revokeObjectURL(next.preview);return;}
      replace(next);
    }catch(error){if(mounted.current&&id===generation.current)onError(error instanceof Error?error.message:'Could not prepare this file.');}
    finally{if(mounted.current&&id===generation.current)setPhase('idle');}
  }
  async function toggleRecording(){
    if(recorder.current?.state==='recording'){recorder.current.stop();setPhase('preparing');return;}
    if(phase!=='idle')return;
    const id=++generation.current;onError('');setPhase('starting');
    try{
      if(!navigator.mediaDevices?.getUserMedia||!window.MediaRecorder)throw new Error('Recording is unavailable. Use HTTPS or localhost, or attach an audio file.');
      const input=await navigator.mediaDevices.getUserMedia({audio:true});
      if(!mounted.current||id!==generation.current){input.getTracks().forEach(track=>track.stop());return;}
      stream.current=input;
      const mime=['audio/webm;codecs=opus','audio/ogg;codecs=opus','audio/mp4','audio/webm'].find(value=>MediaRecorder.isTypeSupported(value));
      const active=mime?new MediaRecorder(input,{mimeType:mime}):new MediaRecorder(input);recorder.current=active;
      const chunks:Blob[]=[];let bytes=0,failed=false;
      active.ondataavailable=event=>{if(event.data.size){bytes+=event.data.size;chunks.push(event.data);}if(bytes>MAX_MEDIA_BYTES&&active.state==='recording')active.stop();};
      active.onerror=()=>{failed=true;onError('Recording failed. Check your microphone or attach an audio file.');releaseCapture();if(active.state!=='inactive')active.stop();setPhase('idle');};
      active.onstop=async()=>{
        releaseCapture();recorder.current=null;
        if(!mounted.current||failed||id!==generation.current)return;
        setPhase('preparing');
        const blob=new Blob(chunks,{type:active.mimeType||mime||'audio/webm'});
        try{const next=await prepareAudio(new File([blob],'Voice message',{type:blob.type}));
          if(mounted.current&&id===generation.current)replace(next);else URL.revokeObjectURL(next.preview);
        }catch(error){if(mounted.current)onError(error instanceof Error?error.message:'Could not prepare the recording.');}
        finally{if(mounted.current)setPhase('idle');}
      };
      active.start(250);setPhase('recording');
      timer.current=window.setTimeout(()=>{if(active.state==='recording'){setPhase('preparing');active.stop();}},30000);
    }catch(error){releaseCapture();recorder.current=null;if(!mounted.current)return;setPhase('idle');
      const name=error&&typeof error==='object'&&'name' in error?String(error.name):'';
      onError(name==='NotAllowedError'?'Allow microphone access in your browser, or attach an audio file.':name==='NotFoundError'?'No microphone was found. Connect one or attach an audio file.':error instanceof Error?error.message:'Microphone access failed.');
    }
  }
  return {attachment,phase,chooseImage:(file?:File)=>choose(file,'image'),chooseAudio:(file?:File)=>choose(file,'audio'),clearAttachment:()=>replace(null),toggleRecording};
}

export function useAssistantSpeech(onError:(message:string)=>void){
  const [speaking,setSpeaking]=useState<number|null>(null),run=useRef(0),utterance=useRef<SpeechSynthesisUtterance|null>(null);
  const audio=useRef<HTMLAudioElement|null>(null),audioUrl=useRef<string|null>(null),pending=useRef<AbortController|null>(null);
  function releaseAudio(){
    if(audio.current){audio.current.onended=null;audio.current.onerror=null;audio.current.pause();audio.current.removeAttribute('src');audio.current=null;}
    if(audioUrl.current)URL.revokeObjectURL(audioUrl.current);audioUrl.current=null;
  }
  function cancel(){run.current++;pending.current?.abort();pending.current=null;window.speechSynthesis?.cancel();utterance.current=null;releaseAudio();}
  useEffect(()=>()=>cancel(),[]);
  function speak(text:string,index:number,conversationId?:string){
    cancel();const id=run.current;
    if(speaking===index){setSpeaking(null);return;}
    onError('');setSpeaking(index);
    function failed(message:string){if(run.current!==id)return;releaseAudio();setSpeaking(null);utterance.current=null;onError(message);}
    async function cloud(offset=0){
      if(run.current!==id)return;
      if(!conversationId){failed('Could not play this reply. Check your browser voice and sound settings.');return;}
      const controller=new AbortController();pending.current=controller;
      try{
        const response=await api.post('/assistant/speech',{conversationId,offset},{timeout:100000,signal:controller.signal});
        if(run.current!==id)return;
        const {mime_type,audio:encoded,nextOffset}=response.data;
        if(mime_type!=='audio/wav'||typeof encoded!=='string'||!(nextOffset===null||Number.isInteger(nextOffset)&&nextOffset>offset))throw new Error('The speech response was invalid.');
        releaseAudio();audioUrl.current=URL.createObjectURL(new Blob([Uint8Array.from(atob(encoded),c=>c.charCodeAt(0))],{type:mime_type}));
        const player=new Audio(audioUrl.current);audio.current=player;
        player.onended=()=>{if(run.current!==id)return;releaseAudio();if(nextOffset===null)setSpeaking(null);else void cloud(nextOffset);};
        player.onerror=()=>failed('Your browser could not play the spoken reply. Check its audio settings.');
        await player.play();
      }catch(error){if(run.current===id)failed(errorMessage(error)||'Could not play this reply. Check your browser voice and sound settings.');}
      finally{if(pending.current===controller)pending.current=null;}
    }
    if(!window.speechSynthesis||!window.SpeechSynthesisUtterance){void cloud();return;}
    const chunks=text.match(/.{1,240}(?:\s|$)|\S{1,240}/gs)||[text];
    function next(){
      if(run.current!==id)return;
      const chunk=chunks.shift();if(!chunk){setSpeaking(null);utterance.current=null;return;}
      const speech=new SpeechSynthesisUtterance(chunk);utterance.current=speech;
      const voices=window.speechSynthesis.getVoices(),language=document.documentElement.lang||'en';
      speech.lang=language;speech.voice=voices.find(voice=>voice.lang?.toLowerCase()===language.toLowerCase())||voices.find(voice=>voice.lang?.split('-')[0]===language.split('-')[0])||null;
      speech.onend=next;speech.onerror=event=>{if(run.current!==id)return;utterance.current=null;if(['canceled','interrupted'].includes(event.error))setSpeaking(null);else void cloud();};
      try{window.speechSynthesis.speak(speech);}catch{void cloud();}
    }
    next();
  }
  return {speaking,speak};
}
