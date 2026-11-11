import {test,expect} from '@playwright/test';
test('hospital registration, administrator approval, hospital profile and responsive workspace',async({page,request})=>{
  const suffix=Date.now().toString();const email=`browser-${suffix}@test.org`,password='Browser-test-password-123!';
  await page.goto('/register');
  await page.getByLabel('Hospital name',{exact:true}).fill(`Browser Hospital ${suffix}`);
  await page.getByLabel('Registration number').fill(`BROWSER-${suffix}`);
  await page.getByLabel('Location',{exact:true}).fill('Addis Ababa');
  await page.getByLabel('Hospital phone').fill('+25111111111');
  await page.getByLabel('Hospital email').fill(`hospital-${suffix}@test.org`);
  await page.getByLabel('Administrator name').fill('Browser Test Admin');
  await page.getByLabel('Administrator email').fill(email);
  await page.getByLabel('Password (12+ characters)').fill(password);
  await page.getByRole('button',{name:'Request registration'}).click();
  await expect(page.getByRole('status')).toContainText('Saved successfully.');
  await page.goto('/login');
  await page.getByLabel('Email address').fill('browser-admin@test.org');await page.getByLabel('Password',{exact:true}).fill(password);
  await page.getByRole('button',{name:'Sign in to workspace'}).click();
  await expect(page.getByRole('heading',{name:'Platform administration'})).toBeVisible();
  const registration=page.locator('details').filter({hasText:`Browser Hospital ${suffix}`});
  await registration.locator('summary').click();await registration.getByRole('button',{name:'Approve / activate'}).click();
  await expect(registration.locator('summary')).toContainText('APPROVED');
  await page.getByRole('button',{name:'Sign out'}).click();
  await page.getByLabel('Email address').fill(email);await page.getByLabel('Password',{exact:true}).fill(password);await page.getByRole('button',{name:'Sign in to workspace'}).click();
  await expect(page.getByRole('heading',{name:'A clearer view of care.'})).toBeVisible();
  await page.getByRole('link',{name:'Hospital profile',exact:true}).click();
  await page.getByLabel('Latitude',{exact:true}).fill('9.03');await page.getByLabel('Longitude',{exact:true}).fill('38.74');await page.getByLabel('Operating hours').fill('24 hours');
  await page.getByRole('button',{name:'Save changes'}).first().click();await expect(page.getByRole('status').first()).toContainText('Saved');
  await page.getByLabel('departments',{exact:true}).fill('Medicine');await page.getByLabel('specialties',{exact:true}).fill('Cardiology');await page.getByLabel('services',{exact:true}).fill('Cardiology');
  await page.getByRole('button',{name:'Save changes'}).nth(1).click();
  await page.getByRole('link',{name:'Operations',exact:true}).click();
  await page.getByLabel('Total beds',{exact:true}).fill('50');await page.getByLabel('Available beds',{exact:true}).fill('12');await page.getByLabel('Staff on duty').fill('15');await page.getByRole('combobox',{name:/Observed workload/}).first().selectOption('Medium');await page.getByLabel('Share capacity').check();
  await page.getByRole('button',{name:'Save changes'}).first().click();await expect(page.getByRole('status').first()).toContainText('Saved');
  await page.getByRole('link',{name:'Overview',exact:true}).click();await expect(page.locator('.capacity-number')).toContainText('12');
  await page.reload();await expect(page.getByRole('heading',{name:'A clearer view of care.'})).toBeVisible();await expect(page.locator('.capacity-number')).toContainText('12');
  await page.screenshot({path:'test-results/desktop-overview.png',fullPage:true});
  await page.setViewportSize({width:390,height:844});await page.screenshot({path:'test-results/mobile-overview.png',fullPage:true});
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
  await page.getByRole('button',{name:'Toggle navigation'}).click();await page.getByRole('link',{name:'Referrals',exact:true}).click();await expect(page.getByRole('heading',{name:'Referrals',exact:true})).toBeVisible();
});

test('human-selected referral completes across two hospital browser sessions',async({page,request})=>{
  const suffix=Date.now(),password='Browser-test-password-123!';
  const login=async(email:string)=>(await request.post('/api/auth/login',{data:{email,password}})).json();
  const system=await login('browser-admin@test.org');const auth=(token:string)=>({Authorization:`Bearer ${token}`});
  const hospitals=[];
  for(const name of ['Sender','Receiver']){
    const email=`${name}-${suffix}@test.org`;
    const r=await request.post('/api/hospitals/register',{data:{name:`${name} ${suffix}`,registrationNumber:`${name}-${suffix}`,location:'Test city',phone:'12345',email,adminName:name,adminEmail:email,password}});expect(r.ok()).toBeTruthy();const h=(await r.json()).hospital;
    await request.patch(`/api/admin/hospitals/${h.id}`,{headers:auth(system.accessToken),data:{status:'APPROVED'}});const account=await login(email);
    await request.post('/api/workspace/catalog',{headers:auth(account.accessToken),data:{departments:['Medicine'],specialties:['Cardiology'],services:[{name:'Cardiology',available:true}],equipment:[]}});hospitals.push({...h,email});
  }
  async function browserLogin(email:string){await page.goto('/login');await page.getByLabel('Email address').fill(email);await page.getByLabel('Password',{exact:true}).fill(password);await page.getByRole('button',{name:'Sign in to workspace'}).click();await expect(page.getByRole('heading',{name:'A clearer view of care.'})).toBeVisible();}
  await browserLogin(hospitals[0].email);await page.getByRole('link',{name:'Referrals',exact:true}).click();await page.getByRole('button',{name:'Create referral'}).click();await page.getByText('Register a patient',{exact:true}).click();
  await page.getByLabel('Hospital patient identifier').fill(`PAT-${suffix}`);await page.getByLabel('Patient name',{exact:true}).fill('Synthetic Browser Patient');await page.getByLabel('Age',{exact:true}).fill('40');await page.getByRole('combobox',{name:/Sex/}).selectOption('Female');await page.getByRole('button',{name:'Save patient'}).click();await expect(page.getByRole('status').first()).toContainText('Saved');
  const patient=page.getByRole('combobox',{name:/Patient/});await expect(patient.locator('option')).toHaveCount(2);await patient.selectOption({index:1});await page.getByLabel('Required service',{exact:true}).fill('Cardiology');await page.getByLabel('Referral clinical summary').fill('Synthetic browser referral for software testing.');await page.getByRole('combobox',{name:/Clinician-assessed urgency/}).selectOption('Routine');await page.getByRole('button',{name:'Create draft & review'}).click();await expect(page.getByRole('heading',{name:'Referral workspace'})).toBeVisible();
  const referralPath=new URL(page.url()).pathname;await page.getByRole('button',{name:'Request AI review'}).click();await expect(page.getByText(/Prediction [a-z0-9-]+/).first()).toBeVisible();
  const destination=page.getByRole('combobox',{name:/Receiving hospital/});await destination.selectOption({label:`${hospitals[1].id} | ${hospitals[1].name}`});await page.getByRole('button',{name:'Submit referral to selected hospital'}).click();await expect(page.getByText('SUBMITTED',{exact:true}).first()).toBeVisible();await page.getByRole('button',{name:'Sign out'}).click();
  await browserLogin(hospitals[1].email);await page.goto(referralPath);await expect(page.getByRole('heading',{name:'Referral workspace'})).toBeVisible();
  for(const status of ['ACCEPTED','IN_PROGRESS','COMPLETED']){await page.getByRole('combobox',{name:/Next status/}).selectOption(status);await page.getByRole('button',{name:'Update referral'}).click();await expect(page.getByText(status,{exact:true}).first()).toBeVisible();}
  await page.getByLabel('Outcome summary').fill('Synthetic completed referral outcome.');await page.getByLabel('Observed delay (minutes)').fill('20');await page.getByRole('button',{name:'Record observed outcome'}).click();await page.getByRole('button',{name:'Verify recorded outcome'}).click();await expect(page.getByText('Verified',{exact:true})).toBeVisible();
});

test('assistant request and cited response render in the hospital workspace',async({page,request})=>{
  const suffix=Date.now().toString(),password='Browser-test-password-123!',email=`assistant-${suffix}@test.org`;
  const login=async(account:string)=>(await request.post('/api/auth/login',{data:{email:account,password}})).json();
  const system=await login('browser-admin@test.org');
  const registration=await request.post('/api/hospitals/register',{data:{
    name:`Assistant Test Hospital ${suffix}`,registrationNumber:`ASSISTANT-${suffix}`,location:'Test city',
    phone:'12345',email:`assistant-hospital-${suffix}@test.org`,adminName:'Assistant Test Admin',adminEmail:email,password,
  }});
  expect(registration.ok()).toBeTruthy();
  const hospital=(await registration.json()).hospital;
  const approval=await request.patch(`/api/admin/hospitals/${hospital.id}`,{headers:{Authorization:`Bearer ${system.accessToken}`},data:{status:'APPROVED'}});
  expect(approval.ok()).toBeTruthy();
  await page.route('**/api/assistant/chat',async route=>{
    const body=route.request().postDataJSON();
    expect(body.question).toBe('What verified information is available?');
    expect(body.threadId).toBeUndefined();
    await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify({thread:{id:'11111111-1111-4111-8111-111111111111',title:body.question,version:1,updatedAt:new Date().toISOString()},conversation:{id:'22222222-2222-4222-8222-222222222222',threadId:'11111111-1111-4111-8111-111111111111',sequence:1,question:body.question,
      answer:'The approved service profile is available on weekdays.',
      sources:[{id:'source-1',source:'Approved test profile',category:'service',updated_at:new Date().toISOString(),content:'The Cardiology clinic is available on weekdays.',stale:false}],
      createdAt:new Date().toISOString(),
    }})});
  });
  await page.goto('/login');
  await page.getByLabel('Email address').fill(email);
  await page.getByLabel('Password',{exact:true}).fill(password);
  await page.getByRole('button',{name:'Sign in to workspace'}).click();
  await page.getByRole('link',{name:'RefHealth AI Assistant'}).click();
  await page.getByRole('textbox',{name:'Message RefHealth AI Assistant'}).fill('What verified information is available?');
  await page.getByRole('button',{name:'Send'}).click();
  await expect(page.getByText('The approved service profile is available on weekdays.')).toBeVisible();
  await page.getByText('Sources (1)').click();
  await expect(page.getByText('The Cardiology clinic is available on weekdays.')).toBeVisible();
});
