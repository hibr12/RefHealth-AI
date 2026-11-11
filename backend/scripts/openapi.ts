import {writeFileSync,mkdirSync} from 'node:fs';
import {buildApp,db} from '../src/app.js';
const app=await buildApp();await app.ready();mkdirSync('docs',{recursive:true});writeFileSync('docs/openapi.json',JSON.stringify(app.swagger(),null,2));await app.close();await db.$disconnect();
