import 'dotenv/config';
import {PrismaClient} from '../generated/prisma/index.js';
import {hashPassword} from '../src/security.js';
const db=new PrismaClient();
const email=process.env.SEED_ADMIN_EMAIL?.toLowerCase(),password=process.env.SEED_ADMIN_PASSWORD;
if(!email||!password||password.length<12)throw new Error('Set SEED_ADMIN_EMAIL and a strong SEED_ADMIN_PASSWORD.');
try {await db.user.upsert({where:{email},create:{email,name:'Platform administrator',passwordHash:await hashPassword(password),role:'SYSTEM_ADMIN',active:true},update:{}});console.log('Platform administrator exists; existing password is unchanged.');}finally{await db.$disconnect();}
