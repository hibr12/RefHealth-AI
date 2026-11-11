// @vitest-environment jsdom
import {afterEach,beforeEach,expect,test,vi} from 'vitest';
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {AxiosHeaders} from 'axios';
import {MemoryRouter} from 'react-router-dom';
import {resetChatFixtures,savedReply,savedHistory} from './assistant-test-support';
import {Assistant} from './pages';
import {api,get} from './api';

vi.mock('./api',()=>({api:{post:vi.fn()},get:vi.fn(),post:vi.fn(),errorMessage:()=>''}));
beforeEach(()=>{vi.clearAllMocks();resetChatFixtures();Object.defineProperty(Element.prototype,'scrollTo',{value:vi.fn(),configurable:true});});
afterEach(cleanup);
async function mount(){const view=render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter><Assistant/></MemoryRouter></QueryClientProvider>);await waitFor(()=>expect((screen.getByLabelText('Message RefHealth AI Assistant') as HTMLTextAreaElement).disabled).toBe(false));return view;}
const reply=(answer:string)=>({data:savedReply(answer),status:200,statusText:'OK',headers:{},config:{headers:new AxiosHeaders()}});

test('short greetings are sent and the reply is displayed',async()=>{
  vi.mocked(api.post).mockResolvedValue(reply('Hello! How can I help?'));
  await mount();
  fireEvent.change(screen.getByLabelText('Message RefHealth AI Assistant'),{target:{value:'hi'}});
  fireEvent.click(screen.getByRole('button',{name:'Send'}));
  await waitFor(()=>expect(screen.getByText('Hello! How can I help?')).toBeTruthy());
  expect(api.post).toHaveBeenCalledWith('/assistant/chat',{question:'hi',clientRequestId:expect.any(String)},{timeout:100000});
});

test('a failed request preserves the draft for a successful retry',async()=>{
  vi.mocked(api.post).mockRejectedValueOnce(new Error('Provider temporarily unavailable')).mockResolvedValueOnce(reply('The desk opens Monday.'));
  await mount();
  const draft=screen.getByLabelText('Message RefHealth AI Assistant') as HTMLTextAreaElement;
  fireEvent.change(draft,{target:{value:'When does our desk open?'}});
  fireEvent.click(screen.getByRole('button',{name:'Send'}));
  await waitFor(()=>expect(screen.getByRole('alert').textContent).toContain('Provider temporarily unavailable'));
  expect(draft.value).toBe('When does our desk open?');
  fireEvent.click(screen.getByRole('button',{name:'Send'}));
  await waitFor(()=>expect(screen.getByText('The desk opens Monday.')).toBeTruthy());
  expect(draft.value).toBe('');
  expect(api.post).toHaveBeenCalledTimes(2);
  expect((vi.mocked(api.post).mock.calls[0][1] as any).clientRequestId).toBe((vi.mocked(api.post).mock.calls[1][1] as any).clientRequestId);
});

test('New chat clears the selected conversation and switching restores only its saved messages',async()=>{
  savedHistory([{id:'old-reply',question:'Older question',answer:'Older answer',sources:[]}]);
  await mount();await screen.findByText('Older answer');
  fireEvent.change(screen.getByLabelText('Message RefHealth AI Assistant'),{target:{value:'Unsent old draft'}});
  fireEvent.click(screen.getByRole('button',{name:'New chat'}));
  await waitFor(()=>expect(screen.queryByText('Older answer')).toBeNull());
  expect((screen.getByLabelText('Message RefHealth AI Assistant') as HTMLTextAreaElement).value).toBe('');
  const body=savedReply('New answer','New topic');body.thread.id='second-thread';body.thread.title='New topic';body.conversation.threadId='second-thread';
  vi.mocked(api.post).mockResolvedValue({...reply('unused'),data:body});
  fireEvent.change(screen.getByLabelText('Message RefHealth AI Assistant'),{target:{value:'New topic'}});fireEvent.click(screen.getByRole('button',{name:'Send'}));
  await screen.findByText('New answer');expect((vi.mocked(api.post).mock.calls[0][1] as any).threadId).toBeUndefined();
  fireEvent.click(screen.getByRole('button',{name:/Test chat/}));await screen.findByText('Older answer');expect(screen.queryByText('New answer')).toBeNull();
});

test('older saved messages load in chronological order',async()=>{
  const thread={id:'thread-test',title:'Long chat',version:3,updatedAt:new Date().toISOString()};
  const turn=(sequence:number)=>({id:'r'+sequence,threadId:thread.id,sequence,question:'Question '+sequence,answer:'Answer '+sequence,sources:[]});
  vi.mocked(get).mockImplementation(async path=>path==='/assistant/threads'?{threads:[thread],nextCursor:null}:path.includes('before=2')?{thread,conversations:[turn(1)],nextBefore:null}:{thread,conversations:[turn(2),turn(3)],nextBefore:2});
  await mount();await screen.findByText('Answer 3');expect(screen.queryByText('Answer 1')).toBeNull();
  fireEvent.click(screen.getByRole('button',{name:'Load earlier messages'}));await screen.findByText('Answer 1');
  expect([...document.querySelectorAll('.chat-message.assistant .chat-bubble > p')].map(p=>p.textContent)).toEqual(['Answer 1','Answer 2','Answer 3']);
  expect(screen.queryByRole('button',{name:'Load earlier messages'})).toBeNull();
});
