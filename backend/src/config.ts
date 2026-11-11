import 'dotenv/config';
import { z } from 'zod';
const webOrigin = z.string().url().refine(value=>{
  try{
    const url=new URL(value);
    return ['http:','https:'].includes(url.protocol)&&url.origin===value;
  }catch{return false;}
},'Use an exact HTTP(S) origin with no path, trailing slash, or credentials.');
export const config = z.object({
  DATABASE_URL: z.string().startsWith('postgresql://'), JWT_SECRET: z.string().min(32),
  PORT: z.coerce.number().default(3000), HOST: z.string().default('127.0.0.1'),
  CORS_ORIGIN: webOrigin.default('http://127.0.0.1:5173'),
  CORS_ADDITIONAL_ORIGINS: z.string().default('').transform(value=>value.split(',').map(origin=>origin.trim()).filter(Boolean)).pipe(z.array(webOrigin)),
  AI_SERVICE_URL: z.string().url().default('http://127.0.0.1:8000'),
  AI_SERVICE_KEY: z.string().default(''), AI_TIMEOUT_MS: z.coerce.number().positive().default(15000),
  AI_ASSISTANT_TIMEOUT_MS: z.coerce.number().int().min(85000).max(95000).default(90000),
  NODE_ENV: z.enum(['development','test','production']).default('development')
}).parse(process.env);
export const trustedOrigins=[...new Set([config.CORS_ORIGIN,...config.CORS_ADDITIONAL_ORIGINS])];
