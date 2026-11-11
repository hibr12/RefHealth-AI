// @vitest-environment jsdom
import {afterEach,beforeEach,expect,test,vi} from 'vitest';
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {QueryClient,QueryClientProvider} from '@tanstack/react-query';
import {MemoryRouter} from 'react-router-dom';
import {IncomingQueue,arrivalFilterUtc,hospitalTime,waitLabel} from './incoming';
import {get,post} from './api';
import {useAuth} from './auth';
vi.mock('./api',()=>({get:vi.fn(),post:vi.fn(),errorMessage:(e:Error)=>e.message}));
vi.mock('./auth',()=>({useAuth:vi.fn()}));
const time='2026-11-11T08:00:00.000Z';
const referral={id:'ref-1',patient:{name:'Synthetic patient',identifier:'TEST-1',age:30,sex:'Unknown'},origin:{id:'origin-1',name:'Referring centre'},requiredService:'Test service',status:'SUBMITTED',urgency:'Routine',clinicalSummary:'Synthetic summary',clinicalObservations:{},submittedAt:time,receivedAt:time,acknowledgedAt:null,confirmedPriority:null,aiPriority:null,assessmentStatus:'DISABLED',priorityExplanation:'Clinical review required.',version:3};
const data={referrals:[referral],total:1,unreviewed:1,serverTime:time,policy:{timezone:'Africa/Nairobi',version:0,deadlines:{},protocol:null,emergencyProcedure:''},facilities:[referral.origin],services:['Test service'],workloadPrediction:null};
beforeEach(()=>{vi.clearAllMocks();vi.mocked(useAuth).mockReturnValue({user:{id:'staff-1',name:'Test clinician',email:'test@example.org',role:'HEALTHCARE_WORKER',hospitalId:'hospital-1',permissions:['REFERRAL_RECEIVE','REFERRAL_TRIAGE']},loading:false,login:vi.fn(),logout:vi.fn()});vi.mocked(get).mockImplementation(async(path)=>path.includes('/events')?{events:[],total:0}:data);vi.mocked(post).mockResolvedValue({success:true});});
afterEach(cleanup);
async function mount(){render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false},mutations:{retry:false}}})}><MemoryRouter><IncomingQueue/></MemoryRouter></QueryClientProvider>);await screen.findByText('Synthetic patient');}
test('timezone display and filters are independent of viewer timezone; unknown arrival is explicit',()=>{
  expect(hospitalTime(time,'Africa/Nairobi')).toContain('11:00:00');
  expect(arrivalFilterUtc('2026-11-11T11:00:00','Africa/Nairobi')).toBe(time);
  expect(arrivalFilterUtc('2026-07-01T09:00:00','America/New_York')).toBe('2026-07-01T13:00:00.000Z');
  expect(waitLabel(null)).toBe('Unknown arrival time');expect(waitLabel(3661)).toBe('1h 1m');
});
test('unassigned priority and disabled AI are visible, and clinician review sends reason and version',async()=>{
  await mount();expect(screen.getByText('CLINICAL REVIEW REQUIRED')).toBeTruthy();expect(screen.getByText(/Automatic clinical priority recommendations are disabled/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button',{name:'Review priority & audit'}));
  fireEvent.change(screen.getByLabelText('Clinician-confirmed priority'),{target:{value:'CRITICAL'}});fireEvent.change(screen.getByLabelText('Clinical review / change reason'),{target:{value:'Reviewed synthetic clinical evidence.'}});
  fireEvent.click(screen.getByRole('button',{name:'Save confirmed priority'}));
  await waitFor(()=>expect(post).toHaveBeenCalledWith('/incoming/ref-1/priority',{priority:'CRITICAL',reason:'Reviewed synthetic clinical evidence.',version:3}));
  expect(screen.queryByRole('button',{name:'Request approved protocol recommendation'})).toBeNull();
});
test('receiving permission alone permits acknowledgement but hides clinical assignment controls',async()=>{
  const actor=useAuth();actor.user!.permissions=['REFERRAL_RECEIVE'];vi.mocked(useAuth).mockReturnValue(actor);await mount();
  fireEvent.click(screen.getByRole('button',{name:'Review priority & audit'}));expect(screen.queryByLabelText('Clinician-confirmed priority')).toBeNull();
  fireEvent.click(screen.getByRole('button',{name:'Acknowledge receipt'}));await waitFor(()=>expect(post).toHaveBeenCalledWith('/incoming/ref-1/acknowledge',{version:3}));
});
test('queue filters are requested from the server and do not sort only the current page',async()=>{
  await mount();fireEvent.change(screen.getByLabelText('Confirmed clinical priority'),{target:{value:'HIGH'}});await waitFor(()=>expect(vi.mocked(get).mock.calls.some(([path])=>path.includes('priority=HIGH'))).toBe(true));
  fireEvent.change(screen.getByLabelText('Arrived from (Africa/Nairobi)'),{target:{value:'2026-11-11T11:00'}});await waitFor(()=>expect(vi.mocked(get).mock.calls.some(([path])=>decodeURIComponent(path).includes('arrivedFrom=2026-11-11T08:00:00.000Z'))).toBe(true));
});
