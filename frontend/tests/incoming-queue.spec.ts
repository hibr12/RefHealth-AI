import {test,expect} from '@playwright/test';
import {randomUUID} from 'node:crypto';
import {mkdirSync} from 'node:fs';

test('receiving queue: policy, clinical review, live ordering, acknowledgement, audit and completion',async({page,request})=>{
  test.skip(process.env.REFHEALTH_QUEUE_BROWSER_TEST!=='1','Requires an isolated coecare_test backend.');
  expect(new URL(process.env.DATABASE_URL||'postgresql://localhost/unconfigured').pathname).toBe('/coecare_test');test.setTimeout(120000);
  const suffix=randomUUID(),password='Browser-test-password-123!';
  const systemLogin=await request.post('/api/auth/login',{data:{email:'browser-admin@test.org',password}});expect(systemLogin.ok()).toBeTruthy();const system=(await systemLogin.json()).accessToken;
  const accounts=[];
  for(const kind of ['sender','receiver']){
    const email=`queue-${kind}-${suffix}@test.org`;
    const registration=await request.post('/api/hospitals/register',{data:{name:`Queue Browser ${kind} ${suffix}`,registrationNumber:`QB-${kind}-${suffix}`,location:'Synthetic city',phone:'000',email,adminName:`Queue ${kind} clinician`,adminEmail:email,password}});expect(registration.ok()).toBeTruthy();const hospital=(await registration.json()).hospital;
    expect((await request.patch(`/api/admin/hospitals/${hospital.id}`,{headers:{Authorization:`Bearer ${system}`},data:{status:'APPROVED'}})).ok()).toBeTruthy();
    const login=await request.post('/api/auth/login',{data:{email,password}});expect(login.ok()).toBeTruthy();const user=await login.json();accounts.push({hospital,email,headers:{Authorization:`Bearer ${user.accessToken}`},user:user.user});
  }
  const [sender,receiver]=accounts;
  expect((await request.post('/api/workspace/catalog',{headers:receiver.headers,data:{departments:[],specialties:[],services:[{name:'Synthetic care',available:true}],equipment:[]}})).ok()).toBeTruthy();
  const clinicianEmail=`queue-clinician-${suffix}@test.org`;
  const clinician=await request.post('/api/workspace/users',{headers:receiver.headers,data:{name:'Authorized synthetic clinical reviewer',email:clinicianEmail,password,role:'HOSPITAL_ADMIN',permissions:['REFERRAL_TRIAGE']}});expect(clinician.ok()).toBeTruthy();
  const clinicianLogin=await request.post('/api/auth/login',{data:{email:clinicianEmail,password}});expect(clinicianLogin.ok()).toBeTruthy();const authorized=await clinicianLogin.json();receiver.email=clinicianEmail;receiver.headers={Authorization:`Bearer ${authorized.accessToken}`};receiver.user=authorized.user;
  await page.goto('/login');await page.getByLabel('Email address').fill(receiver.email);await page.getByLabel('Password',{exact:true}).fill(password);await page.getByRole('button',{name:'Sign in to workspace'}).click();
  await page.getByRole('link',{name:'Incoming queue',exact:true}).click();await expect(page.getByRole('heading',{name:'Incoming referrals',exact:true})).toBeVisible();
  await expect(page.getByText(/Automatic clinical priority recommendations are disabled/)).toBeVisible();
  await page.locator('summary').filter({hasText:'Hospital queue policy'}).click();await page.getByRole('spinbutton',{name:'CRITICAL deadline minutes',exact:true}).fill('2');await page.getByRole('spinbutton',{name:'CRITICAL warning minutes',exact:true}).fill('1');await page.getByRole('spinbutton',{name:'LOW deadline minutes',exact:true}).fill('60');await page.getByRole('spinbutton',{name:'LOW warning minutes',exact:true}).fill('10');await page.getByLabel('Approved emergency escalation procedure').fill('Synthetic test: contact the assigned clinical lead.');await page.getByRole('button',{name:'Save hospital queue policy'}).click();await expect(page.getByText('Queue policy saved for future arrivals.')).toBeVisible();await page.locator('summary').filter({hasText:'Hospital queue policy'}).click();
  async function send(name:string){
    const p=await request.post('/api/patients',{headers:sender.headers,data:{identifier:randomUUID(),name,age:30,sex:'Unknown'}});expect(p.ok()).toBeTruthy();
    const draft=await request.post('/api/referrals',{headers:sender.headers,data:{patientId:(await p.json()).patient.id,requiredService:'Synthetic care',clinicalSummary:'Synthetic patient for browser validation.',urgency:'Routine'}});expect(draft.ok()).toBeTruthy();const r=(await draft.json()).referral;
    const submit=await request.post(`/api/referrals/${r.id}/transition`,{headers:sender.headers,data:{status:'SUBMITTED',destinationId:receiver.hospital.id,version:r.version}});expect(submit.ok()).toBeTruthy();return (await submit.json()).referral;
  }
  const earlier=await send('Earlier synthetic patient'),later=await send('Later synthetic patient');
  await expect(page.locator('.queue-card')).toHaveCount(2,{timeout:15000});
  async function assign(name:string,priority:string){const card=page.locator('.queue-card').filter({hasText:name});await card.getByRole('button',{name:'Review priority & audit'}).click();await card.getByLabel('Clinician-confirmed priority').selectOption(priority);await card.getByLabel('Clinical review / change reason').fill('Synthetic clinician review with documented evidence.');await card.getByRole('button',{name:'Save confirmed priority'}).click();await expect(card.locator('.queue-priority')).toContainText(priority);await expect(card.locator('.queue-audit')).toContainText('Synthetic clinician review');await card.getByRole('button',{name:'Close review & audit'}).click();}
  await assign('Earlier synthetic patient','LOW');await assign('Later synthetic patient','CRITICAL');await expect(page.locator('.queue-card').first()).toContainText('Later synthetic patient');
  await page.getByRole('combobox',{name:'Confirmed clinical priority',exact:true}).selectOption('LOW');await expect(page.locator('.queue-card')).toHaveCount(1);await expect(page.locator('.queue-card')).toContainText('Earlier synthetic patient');await page.getByRole('button',{name:'Clear filters'}).click();await expect(page.locator('.queue-card')).toHaveCount(2);
  const critical=page.locator('.queue-card').filter({hasText:'Later synthetic patient'});await critical.getByRole('button',{name:'Acknowledge receipt'}).click();await expect(critical.getByRole('button',{name:'Acknowledge receipt'})).toHaveCount(0);await expect(critical).toContainText('Wait until acknowledged');
  mkdirSync('../.local/incoming-queue',{recursive:true});await page.screenshot({path:'../.local/incoming-queue/desktop.png',fullPage:true});await page.setViewportSize({width:390,height:844});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();await page.screenshot({path:'../.local/incoming-queue/mobile.png',fullPage:true});await page.setViewportSize({width:1280,height:900});
  await critical.getByRole('link',{name:'Open referral workflow'}).click();
  for(const status of ['ACCEPTED','IN_PROGRESS','COMPLETED']){await page.getByLabel('Next status').selectOption(status);const response=page.waitForResponse(r=>r.url().endsWith(`/api/referrals/${later.id}/transition`)&&r.request().method()==='POST');await page.getByRole('button',{name:'Update referral'}).click();expect((await response).ok()).toBeTruthy();await expect(page.locator('.badge').first()).toHaveText(status);}
  const saved=await request.get(`/api/referrals/${later.id}`,{headers:receiver.headers});const final=(await saved.json()).referral;expect(final.receivedAt).toBe(later.receivedAt);expect(final.acknowledgedAt).toBeTruthy();
  await page.getByRole('link',{name:'Incoming queue',exact:true}).click();await expect(page.locator('.queue-card')).toHaveCount(1);const newArrival=await send('Polling synthetic patient');await expect(page.locator('.queue-card')).toHaveCount(2,{timeout:15000});await expect(page.locator('.queue-card').filter({hasText:'Polling synthetic patient'})).toContainText('CLINICAL REVIEW REQUIRED');
  expect(earlier.id).not.toBe(newArrival.id);await page.reload();await expect(page.locator('.queue-card')).toHaveCount(2);
});
