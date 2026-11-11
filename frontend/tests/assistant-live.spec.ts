import {test,expect,type Page,type APIRequestContext} from '@playwright/test';
import {randomUUID} from 'node:crypto';

test.beforeEach(()=>{
  test.skip(process.env.REFHEALTH_LIVE_PROVIDER_TEST!=='1','Opt in only with an isolated test stack and configured provider keys.');
  test.setTimeout(480000);
  expect(new URL(process.env.DATABASE_URL||'postgresql://localhost/unconfigured').pathname).toBe('/coecare_test');
});

async function assistantWorkspace(page:Page,request:APIRequestContext){
  const suffix=randomUUID(),password='Browser-test-password-123!',email=`live-assistant-${suffix}@test.org`;
  const login=async(account:string)=>{
    const response=await request.post('/api/auth/login',{data:{email:account,password}});
    expect(response.ok()).toBeTruthy();
    return response.json();
  };
  const system=await login('browser-admin@test.org');
  const registration=await request.post('/api/hospitals/register',{data:{
    name:`Synthetic Assistant Hospital ${suffix}`,registrationNumber:`LIVE-${suffix}`,location:'Synthetic test city',
    phone:'12345',email,adminName:'Synthetic Assistant Admin',adminEmail:email,password,
  }});
  expect(registration.ok()).toBeTruthy();
  const hospital=(await registration.json()).hospital;
  const approval=await request.patch(`/api/admin/hospitals/${hospital.id}`,{
    headers:{Authorization:`Bearer ${system.accessToken}`},data:{status:'APPROVED'},
  });
  expect(approval.ok()).toBeTruthy();
  const account=await login(email),headers={Authorization:`Bearer ${account.accessToken}`};
  const content='Synthetic test notice: the coordination desk for this hospital opens Monday to Friday from 09:00 to 17:00. RefHealth AI supports referral acknowledgement delay prediction, hospital recommendation, and next-day hospital workload prediction. Real operational delay and workload predictions require approved models and sufficient verified data; they are not approved automatically.';
  const proposal=await request.post('/api/knowledge',{headers,data:{
    category:'operational',content,source:'Synthetic live assistant verification notice',visibility:'PRIVATE',
  }});
  expect(proposal.ok()).toBeTruthy();
  const record=(await proposal.json()).record;
  const review=await request.post(`/api/knowledge/${record.id}/review`,{headers,data:{
    decision:'APPROVED',reason:'Synthetic software test fixture, not real hospital information.',
  }});
  expect(review.ok()).toBeTruthy();

  await page.goto('/login');
  await page.getByLabel('Email address').fill(email);
  await page.getByLabel('Password',{exact:true}).fill(password);
  await page.getByRole('button',{name:'Sign in to workspace'}).click();
  await page.getByRole('link',{name:'RefHealth AI Assistant'}).click();

  async function ask(question:string,historyLength:number,requireCitation=true,expectedCitation:string|null=record.id){
    const responsePromise=page.waitForResponse(response=>response.url().endsWith('/api/assistant/chat')&&response.request().method()==='POST',{timeout:100000});
    await page.getByRole('textbox',{name:'Message RefHealth AI Assistant'}).fill(question);
    await page.getByRole('button',{name:'Send',exact:true}).click();
    const response=await responsePromise;
    const submitted=response.request().postDataJSON();
    if(historyLength){expect(submitted.threadId).toEqual(expect.any(String));expect(submitted.expectedVersion).toBe(historyLength/2);}else expect(submitted.threadId).toBeUndefined();
    const body=await response.json();
    expect(response.status(),JSON.stringify(body.error)).toBe(200);
    if(requireCitation){
      if(expectedCitation===null)expect(body.conversation.sources.length).toBeGreaterThan(0);
      else expect(body.conversation.sources.some((source:{id:string})=>source.id===expectedCitation)).toBeTruthy();
    }else expect(body.conversation.sources).toEqual([]);
    await expect(page.locator('.chat-message.assistant').last()).toContainText(body.conversation.answer);
    return body.conversation.answer as string;
  }
  async function approvedDirectory(){
    const hospitals:{id:string;name:string}[]=[];
    for(let currentPage=1;;currentPage++){
      const response=await request.get(`/api/hospitals?limit=100&page=${currentPage}`,{headers});
      expect(response.ok()).toBeTruthy();
      const batch=(await response.json()).hospitals;
      hospitals.push(...batch);
      if(batch.length<100)return hospitals;
    }
  }
  return {ask,content,approvedDirectory};
}

test('live hospital count, purpose and active hospital list succeed and persist',async({page,request})=>{
  const {ask,approvedDirectory}=await assistantWorkspace(page,request);
  const hospitals=await approvedDirectory();
  const hospitalAnswer=await ask('how many hospitals are registered in this system',0,true,null);
  expect(hospitalAnswer).toMatch(new RegExp(`\\b${hospitals.length}\\b`));
  const purpose=await ask('ok what is your purpose in this system',2,false);
  expect(purpose).toMatch(/coordination|referral|hospital/i);
  const active=await ask('which are the active hospital currently',4,true,'system:approved-hospital-directory:1');
  for(const hospital of hospitals)expect(active).toContain(hospital.name);
  await expect(page.getByRole('alert')).toHaveCount(0);
  await page.reload();
  await expect(page.locator('.chat-message.assistant')).toHaveCount(3);
  await expect(page.locator('.chat-message.assistant').last()).toContainText(active);
});

test('live Gemini retrieval and Groq replies persist with conversation history',async({page,request})=>{
  const {ask,content}=await assistantWorkspace(page,request);
  const components=await ask('According to our approved notice, which three AI components does RefHealth AI support?',0);
  expect(components).toMatch(/delay/i);
  expect(components).toMatch(/recommend/i);
  expect(components).toMatch(/workload/i);
  const hours=await ask('According to our approved notice, on which days does our coordination desk open?',2);
  expect(hours).toMatch(/Monday/i);
  expect(hours).toMatch(/Friday/i);
  const followup=await ask('For the coordination desk we just discussed, repeat the days it opens.',4);
  expect(followup).toMatch(/Monday/i);
  expect(followup).toMatch(/Friday/i);
  await page.locator('.chat-message.assistant').last().locator('summary').click();
  await expect(page.locator('.chat-message.assistant').last()).toContainText(content);
  await page.reload();
  await expect(page.locator('.chat-message.assistant')).toHaveCount(3);
  await expect(page.locator('.chat-message.assistant').last()).toContainText(followup);
  const greeting=await ask('hi',6,false);
  expect(greeting.trim().length).toBeGreaterThan(0);
  await page.reload();
  await expect(page.locator('.chat-message.assistant')).toHaveCount(4);
  await expect(page.locator('.chat-message.assistant').last()).toContainText(greeting);
});
