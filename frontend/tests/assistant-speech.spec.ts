import {test,expect} from '@playwright/test';
import {createRequire} from 'node:module';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';

// Reuses only synthetic media accounts created by assistant-media-live.spec.ts.
test.beforeEach(()=>{
  test.skip(process.env.REFHEALTH_SPEECH_TEST!=='1','Requires the isolated media-test workspace.');
  expect(new URL(process.env.DATABASE_URL||'postgresql://localhost/unconfigured').pathname).toBe('/coecare_test');
});
test.use({launchOptions:{executablePath:process.env.CHROME_PATH||'C:/Program Files/Google/Chrome/Application/chrome.exe'}});

async function account(){
  const {PrismaClient}=createRequire(import.meta.url)('../../backend/generated/prisma');
  const db=new PrismaClient();
  try{
    const owners=await db.conversation.findMany({select:{userId:true},distinct:['userId'],take:100});
    const user=await db.user.findFirstOrThrow({where:{id:{in:owners.map((row:any)=>row.userId)},email:{startsWith:'media-'},role:'HOSPITAL_ADMIN',active:true},orderBy:{createdAt:'desc'},select:{email:true}});
    return user.email;
  }finally{await db.$disconnect();}
}

test('cloud reply audio decodes and plays in the browser, and Stop releases it',async({page})=>{
  const email=await account();
  await page.addInitScript(()=>{
    Object.defineProperty(window,'speechSynthesis',{value:undefined,configurable:true});
    const NativeAudio=window.Audio;
    window.Audio=function(src?:string){const audio=new NativeAudio(src);(window as any).__replyAudio=audio;return audio;} as unknown as typeof Audio;
  });
  const wave=readFileSync(resolve(process.env.REFHEALTH_TEST_AUDIO_FILE||'../.local/assistant-media/question.wav')).toString('base64');
  // Provider output is a known WAV here: verifies decoding/playback, not synthesis.
  await page.route('**/api/assistant/speech',route=>route.fulfill({json:{mime_type:'audio/wav',audio:wave,nextOffset:null}}));
  await page.goto('/login');await page.getByLabel('Email address').fill(email);await page.getByLabel('Password',{exact:true}).fill('Browser-test-password-123!');
  await page.getByRole('button',{name:'Sign in to workspace'}).click();await page.getByRole('link',{name:'RefHealth AI Assistant'}).click();
  const request=page.waitForRequest('**/api/assistant/speech');
  await page.getByRole('button',{name:'Read answer aloud'}).last().click();
  expect((await request).postDataJSON()).toMatchObject({conversationId:expect.any(String),offset:0});
  await expect.poll(()=>page.evaluate(()=>(window as any).__replyAudio?.currentTime||0)).toBeGreaterThan(0);
  await page.getByRole('button',{name:'Stop reading aloud'}).click();
  expect(await page.evaluate(()=>(window as any).__replyAudio.paused)).toBe(true);
  await expect(page.getByRole('button',{name:'Stop reading aloud'})).toHaveCount(0);
});

test('real cloud speech reports the provider setup requirement without losing the reply',async({page})=>{
  test.skip(process.env.REFHEALTH_EXPECT_SPEECH_TERMS!=='1','Only for reproducing the current unaccepted Groq model terms.');
  test.setTimeout(110000);
  const email=await account();
  await page.addInitScript(()=>Object.defineProperty(window,'speechSynthesis',{value:undefined,configurable:true}));
  await page.goto('/login');await page.getByLabel('Email address').fill(email);await page.getByLabel('Password',{exact:true}).fill('Browser-test-password-123!');
  await page.getByRole('button',{name:'Sign in to workspace'}).click();await page.getByRole('link',{name:'RefHealth AI Assistant'}).click();
  const reply=page.locator('.chat-message.assistant').last(),text=await reply.locator('.chat-bubble > p').innerText();
  const response=page.waitForResponse('**/api/assistant/speech',{timeout:100000});
  await reply.getByRole('button',{name:'Read answer aloud'}).click();expect((await response).status()).toBe(503);
  await expect(page.getByRole('alert')).toContainText('model terms');
  await expect(reply).toContainText(text);await expect(page.getByRole('button',{name:'Stop reading aloud'})).toHaveCount(0);
});
