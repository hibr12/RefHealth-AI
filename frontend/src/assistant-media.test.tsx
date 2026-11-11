// @vitest-environment jsdom
import {afterEach,beforeEach,expect,test,vi} from 'vitest';
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {AxiosHeaders} from 'axios';
import {MemoryRouter} from 'react-router-dom';
import {resetChatFixtures,savedReply,savedHistory} from './assistant-test-support';
import {Assistant} from './pages';
import {api,get} from './api';

vi.mock('./api',()=>({api:{post:vi.fn()},get:vi.fn(),post:vi.fn(),errorMessage:()=>''}));
beforeEach(()=>{
  vi.clearAllMocks();resetChatFixtures();
  Object.defineProperty(Element.prototype,'scrollTo',{value:vi.fn(),configurable:true});
  Object.defineProperty(URL,'createObjectURL',{value:vi.fn(()=> 'blob:test-audio'),configurable:true});
  Object.defineProperty(URL,'revokeObjectURL',{value:vi.fn(),configurable:true});
});
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals();});
async function mount(){const view=render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter><Assistant/></MemoryRouter></QueryClientProvider>);await waitFor(()=>expect((screen.getByLabelText('Message RefHealth AI Assistant') as HTMLTextAreaElement).disabled).toBe(false));return view;}
function reply(answer:string,question?:string){return {data:savedReply(answer,question),status:200,statusText:'OK',headers:{},config:{headers:new AxiosHeaders()}};}
function input(accept:string){return document.querySelector(`input[type="file"][accept*="${accept}"]`) as HTMLInputElement;}

test('image preparation blocks sending until compressed bytes are ready',async()=>{
  let finish!:(value:any)=>void;
  vi.stubGlobal('createImageBitmap',vi.fn(()=>new Promise(resolve=>{finish=resolve;})));
  vi.spyOn(HTMLCanvasElement.prototype,'getContext').mockReturnValue({fillRect:vi.fn(),drawImage:vi.fn()} as any);
  vi.spyOn(HTMLCanvasElement.prototype,'toBlob').mockImplementation(callback=>callback(new Blob(['compressed image'],{type:'image/jpeg'})));
  vi.mocked(api.post).mockResolvedValue(reply('A blue circle.'));
  await mount();fireEvent.change(screen.getByLabelText('Message RefHealth AI Assistant'),{target:{value:'Describe this image.'}});
  fireEvent.change(input('image/jpeg'),{target:{files:[new File(['image'],'circle.png',{type:'image/png'})]}});
  expect((screen.getByRole('button',{name:'Send'}) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.submit(document.querySelector('.chat-composer')!);expect(api.post).not.toHaveBeenCalled();
  const close=vi.fn();await act(async()=>finish({width:200,height:200,close}));
  await waitFor(()=>expect((screen.getByRole('button',{name:'Send'}) as HTMLButtonElement).disabled).toBe(false));
  expect(close).toHaveBeenCalledOnce();
  fireEvent.click(screen.getByRole('button',{name:'Send'}));
  await waitFor(()=>expect(api.post).toHaveBeenCalled());
  expect(vi.mocked(api.post).mock.calls[0][1]).toMatchObject({attachment:{mime_type:'image/jpeg',data:btoa('compressed image')}});
});

test('audio upload normalizes M4A and keeps the transcript in subsequent history',async()=>{
  vi.mocked(api.post).mockResolvedValueOnce(reply('I help with coordination.','What is your purpose?')).mockResolvedValueOnce(reply('I can explain referrals.'));
  await mount();fireEvent.change(input('.wav'),{target:{files:[new File(['voice'],'question.m4a',{type:'audio/x-m4a'})]}});
  await waitFor(()=>expect((screen.getByRole('button',{name:'Send'}) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(screen.getByRole('button',{name:'Send'}));
  await screen.findByText('What is your purpose?');
  expect(vi.mocked(api.post).mock.calls[0][1]).toMatchObject({attachment:{mime_type:'audio/mp4',data:btoa('voice')}});
  fireEvent.change(screen.getByLabelText('Message RefHealth AI Assistant'),{target:{value:'Tell me more.'}});
  fireEvent.click(screen.getByRole('button',{name:'Send'}));
  await waitFor(()=>expect(api.post).toHaveBeenCalledTimes(2));
  expect(vi.mocked(api.post).mock.calls[1][1]).toMatchObject({threadId:'thread-test',expectedVersion:1});
  expect(URL.revokeObjectURL).toHaveBeenCalledWith('blob:test-audio');
});

test('empty and oversized audio files are rejected before submission',async()=>{
  await mount();fireEvent.change(input('.wav'),{target:{files:[new File([],'empty.wav',{type:'audio/wav'})]}});
  await waitFor(()=>expect(screen.getByRole('alert').textContent).toContain('No audio was captured'));
  fireEvent.change(input('.wav'),{target:{files:[new File([new Uint8Array(4*1024*1024+1)],'large.wav',{type:'audio/wav'})]}});
  await waitFor(()=>expect(screen.getByRole('alert').textContent).toContain('smaller than 4 MB'));
  expect(api.post).not.toHaveBeenCalled();
});

function microphone(getUserMedia:()=>Promise<any>){
  Object.defineProperty(navigator,'mediaDevices',{value:{getUserMedia},configurable:true});
  class Recorder {
    static isTypeSupported(mime:string){return mime.startsWith('audio/webm');}
    state='inactive';mimeType='audio/webm;codecs=opus';onstop:any;ondataavailable:any;onerror:any;
    start(){this.state='recording';}
    stop(){this.state='inactive';this.ondataavailable?.({data:new Blob(['captured voice'],{type:this.mimeType})});void this.onstop?.();}
  }
  vi.stubGlobal('MediaRecorder',Recorder);
}

test('microphone denial offers recovery and releases the waiting state',async()=>{
  microphone(async()=>{throw new DOMException('Denied','NotAllowedError');});
  await mount();fireEvent.click(screen.getByRole('button',{name:'Record voice message'}));
  await waitFor(()=>expect(screen.getByRole('alert').textContent).toContain('Allow microphone access'));
  expect((screen.getByRole('button',{name:'Attach audio'}) as HTMLButtonElement).disabled).toBe(false);
});

test('recording blocks submission and stops microphone tracks before preview',async()=>{
  const stop=vi.fn();microphone(async()=>({getTracks:()=>[{stop}]}));
  await mount();fireEvent.change(screen.getByLabelText('Message RefHealth AI Assistant'),{target:{value:'Listen to this.'}});
  fireEvent.click(screen.getByRole('button',{name:'Record voice message'}));
  await screen.findByRole('button',{name:'Stop recording'});
  expect((screen.getByRole('button',{name:'Send'}) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('button',{name:'Stop recording'}));
  await waitFor(()=>expect(document.querySelector('.chat-attachment-preview audio')).toBeTruthy());
  expect(stop).toHaveBeenCalledOnce();expect(api.post).not.toHaveBeenCalled();
});

test('leaving while microphone permission is pending stops the late stream',async()=>{
  let finish!:(value:any)=>void;const stop=vi.fn();microphone(()=>new Promise(resolve=>{finish=resolve;}));
  const view=await mount();fireEvent.click(screen.getByRole('button',{name:'Record voice message'}));view.unmount();
  await act(async()=>finish({getTracks:()=>[{stop}]}));
  expect(stop).toHaveBeenCalledOnce();
});

test('spoken replies can be stopped and playback failures are visible',async()=>{
  const speech={cancel:vi.fn(),speak:vi.fn(),getVoices:()=>[]};vi.stubGlobal('speechSynthesis',speech);
  vi.stubGlobal('SpeechSynthesisUtterance',class {text:string;constructor(text:string){this.text=text;}});
  vi.mocked(api.post).mockResolvedValue(reply('Hello! I can help with coordination.'));
  await mount();fireEvent.change(screen.getByLabelText('Message RefHealth AI Assistant'),{target:{value:'hi'}});fireEvent.click(screen.getByRole('button',{name:'Send'}));
  const listen=await screen.findByRole('button',{name:'Read answer aloud'}),cancels=speech.cancel.mock.calls.length;fireEvent.click(listen);
  expect(speech.speak).toHaveBeenCalledOnce();expect(speech.speak.mock.calls[0][0].text).toContain('coordination');
  fireEvent.click(screen.getByRole('button',{name:'Stop reading aloud'}));expect(speech.cancel).toHaveBeenCalledTimes(cancels+2);
  fireEvent.click(screen.getByRole('button',{name:'Read answer aloud'}));
  act(()=>speech.speak.mock.calls[1][0].onerror({error:'voice-unavailable'}));
  await waitFor(()=>expect(screen.getByRole('alert').textContent).toContain('voice and sound settings'));
});

test('failed browser speech uses authorized cloud segments and Stop releases playback',async()=>{
  const speech={cancel:vi.fn(),speak:vi.fn(),getVoices:()=>[{lang:'ar-SA',default:true},{lang:'en-GB',default:false}]};vi.stubGlobal('speechSynthesis',speech);
  vi.stubGlobal('SpeechSynthesisUtterance',class {});
  const players:any[]=[];
  vi.stubGlobal('Audio',class {play=vi.fn(async()=>{});pause=vi.fn();removeAttribute=vi.fn();onended:any;onerror:any;constructor(){players.push(this);}});
  savedHistory([{id:'private-reply',question:'Hello',answer:'Hello, I help with referrals.',sources:[]}]);
  vi.mocked(api.post).mockResolvedValueOnce({data:{mime_type:'audio/wav',audio:btoa('wav segment'),nextOffset:100}} as any).mockResolvedValueOnce({data:{mime_type:'audio/wav',audio:btoa('last segment'),nextOffset:null}} as any);
  await mount();fireEvent.click(await screen.findByRole('button',{name:'Read answer aloud'}));
  expect(speech.speak.mock.calls[0][0].voice.lang).toBe('en-GB');
  act(()=>speech.speak.mock.calls[0][0].onerror({error:'synthesis-failed'}));
  await waitFor(()=>expect(players[0]?.play).toHaveBeenCalledOnce());
  expect(api.post).toHaveBeenCalledWith('/assistant/speech',{conversationId:'private-reply',offset:0},expect.objectContaining({signal:expect.any(AbortSignal)}));
  act(()=>players[0].onended());
  await waitFor(()=>expect(players[1]?.play).toHaveBeenCalledOnce());
  expect(vi.mocked(api.post).mock.calls[1][1]).toEqual({conversationId:'private-reply',offset:100});
  fireEvent.click(screen.getByRole('button',{name:'Stop reading aloud'}));
  expect(players[1].pause).toHaveBeenCalledOnce();expect(URL.revokeObjectURL).toHaveBeenCalled();
});

test('leaving cancels pending cloud speech without starting late audio',async()=>{
  vi.stubGlobal('speechSynthesis',undefined);vi.stubGlobal('Audio',vi.fn());
  savedHistory([{id:'private-reply',question:'Hello',answer:'Hello!',sources:[]}]);
  let finish!:(value:any)=>void;vi.mocked(api.post).mockImplementation(()=>new Promise(resolve=>{finish=resolve;}));
  const view=await mount();fireEvent.click(await screen.findByRole('button',{name:'Read answer aloud'}));
  const signal=vi.mocked(api.post).mock.calls[0][2]?.signal;
  view.unmount();expect(signal?.aborted).toBe(true);
  await act(async()=>finish({data:{mime_type:'audio/wav',audio:btoa('wave'),nextOffset:null}}));
  expect(Audio).not.toHaveBeenCalled();
});
