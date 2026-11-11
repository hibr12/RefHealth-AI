import {test,expect,type Page,type APIRequestContext} from '@playwright/test';
import {randomUUID} from 'node:crypto';
import {resolve} from 'node:path';
import {existsSync} from 'node:fs';

const wave=resolve(process.env.REFHEALTH_TEST_AUDIO_FILE||'../.local/assistant-media/question.wav');
const picture=resolve(process.env.REFHEALTH_TEST_IMAGE_FILE||'../.local/assistant-media/blue-circle.png');
test.use({launchOptions:{executablePath:process.env.CHROME_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe',args:['--use-fake-ui-for-media-stream','--use-fake-device-for-media-stream',`--use-file-for-fake-audio-capture=${wave}`]},permissions:['microphone']});
test.beforeEach(()=>{
  test.skip(process.env.REFHEALTH_LIVE_MEDIA_TEST!=='1','Requires configured real media providers and an isolated test database.');
  test.setTimeout(420000);
  expect(new URL(process.env.DATABASE_URL||'postgresql://localhost/unconfigured').pathname).toBe('/coecare_test');
  expect(existsSync(wave)).toBeTruthy();expect(existsSync(picture)).toBeTruthy();
});

async function workspace(page:Page,request:APIRequestContext){
  const password='Browser-test-password-123!',suffix=randomUUID(),email=`media-${suffix}@test.org`;
  const login=await request.post('/api/auth/login',{data:{email:'browser-admin@test.org',password}});expect(login.ok()).toBeTruthy();
  const system=await login.json();
  const registration=await request.post('/api/hospitals/register',{data:{name:`Synthetic Media Hospital ${suffix}`,registrationNumber:`MEDIA-${suffix}`,location:'Synthetic city',phone:'12345',email,adminName:'Synthetic Media Admin',adminEmail:email,password}});expect(registration.ok()).toBeTruthy();
  const hospital=(await registration.json()).hospital;
  const approval=await request.patch(`/api/admin/hospitals/${hospital.id}`,{headers:{Authorization:`Bearer ${system.accessToken}`},data:{status:'APPROVED'}});expect(approval.ok()).toBeTruthy();
  await page.goto('/login');await page.getByLabel('Email address').fill(email);await page.getByLabel('Password',{exact:true}).fill(password);await page.getByRole('button',{name:'Sign in to workspace'}).click();await page.getByRole('link',{name:'RefHealth AI Assistant'}).click();
}
async function send(page:Page){
  const pending=page.waitForResponse(response=>response.url().endsWith('/api/assistant/chat')&&response.request().method()==='POST',{timeout:100000});
  await expect(page.getByRole('button',{name:'Send',exact:true})).toBeEnabled();await page.getByRole('button',{name:'Send',exact:true}).click();
  const response=await pending,body=await response.json();expect(response.status(),JSON.stringify(body.error)).toBe(200);
  await expect(page.locator('.chat-message.assistant').last()).toContainText(body.conversation.answer);
  return {conversation:body.conversation,submitted:response.request().postDataJSON()};
}

test('live image upload, visual answer and follow-up survive reload',async({page,request})=>{
  await workspace(page,request);
  await page.locator('input[type=file][accept*="image/jpeg"]').setInputFiles(picture);
  await expect(page.getByAltText('Selected image preview')).toBeVisible();
  await page.getByRole('textbox',{name:'Message RefHealth AI Assistant'}).fill('Describe the simple shape and its color in this test image.');
  const image=await send(page);expect(image.submitted.attachment.mime_type).toBe('image/jpeg');
  expect(image.conversation.answer).toMatch(/blue/i);expect(image.conversation.answer).toMatch(/circle/i);
  await page.getByRole('textbox',{name:'Message RefHealth AI Assistant'}).fill('Repeat the color you described in your previous answer.');
  const followup=await send(page);expect(followup.submitted.threadId).toBe(image.conversation.threadId);expect(followup.submitted.expectedVersion).toBe(1);expect(followup.conversation.answer).toMatch(/blue/i);
  await page.reload();await expect(page.locator('.chat-message.assistant')).toHaveCount(2);
  await expect(page.locator('.chat-message.assistant').last()).toContainText(followup.conversation.answer);
});

test('live audio upload and microphone recording keep transcripts and offer playback',async({page,request})=>{
  await page.addInitScript(()=>{
    const events:string[]=[];(window as any).__speechEvents=events;
    const native=window.speechSynthesis.speak.bind(window.speechSynthesis);
    window.speechSynthesis.speak=utterance=>{events.push('requested');utterance.addEventListener('start',()=>events.push('started'));utterance.addEventListener('error',event=>events.push(`error:${event.error}`));native(utterance);};
  });
  await workspace(page,request);
  await page.locator('input[type=file][accept*=".wav"]').setInputFiles(wave);
  await expect(page.locator('.chat-attachment-preview audio')).toBeVisible();
  const uploaded=await send(page);expect(uploaded.submitted.attachment.mime_type).toBe('audio/wav');
  expect(uploaded.conversation.question).toMatch(/country/i);
  await expect(page.locator('.chat-message.user').last()).toContainText(uploaded.conversation.question);
  await page.getByRole('button',{name:'Record voice message'}).click();
  await expect(page.getByRole('button',{name:'Stop recording'})).toBeVisible();
  await expect(page.getByRole('button',{name:'Send',exact:true})).toBeDisabled();
  // Capture the entire 11-second public speech fixture through real MediaRecorder.
  await page.waitForTimeout(12000);await page.getByRole('button',{name:'Stop recording'}).click();
  await expect(page.locator('.chat-attachment-preview audio')).toBeVisible();
  const recorded=await send(page);expect(recorded.submitted.attachment.mime_type).toBe('audio/webm');
  expect(recorded.conversation.question).toMatch(/country/i);
  expect(recorded.submitted.threadId).toBe(uploaded.conversation.threadId);expect(recorded.submitted.expectedVersion).toBe(1);
  await page.reload();await expect(page.locator('.chat-message.assistant')).toHaveCount(2);
  await expect(page.locator('.chat-message.user').last()).toContainText(recorded.conversation.question);
  await page.locator('.chat-message.assistant').last().getByRole('button',{name:'Read answer aloud'}).click();
  await expect.poll(()=>page.evaluate(()=>(window as any).__speechEvents)).toContain('requested');
  const stop=page.getByRole('button',{name:'Stop reading aloud'});
  if(await stop.isVisible())await stop.click();
  await expect(page.getByRole('button',{name:'Stop reading aloud'})).toHaveCount(0);
  await test.info().attach('speech-engine-events',{body:JSON.stringify(await page.evaluate(()=>(window as any).__speechEvents)),contentType:'application/json'});
});
