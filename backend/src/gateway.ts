import { config } from './config.js';
import { ApiError } from './security.js';
export async function ai(path: string,body?: unknown,timeoutMs=config.AI_TIMEOUT_MS) {
  if (!config.AI_SERVICE_KEY) throw new ApiError(503,'AI service authentication is not configured.');
  try {
    const response = await fetch(new URL(path,config.AI_SERVICE_URL),{method:body?'POST':'GET',
      headers:{'Content-Type':'application/json','X-API-Key':config.AI_SERVICE_KEY},
      body:body?JSON.stringify(body):undefined,signal:AbortSignal.timeout(timeoutMs)});
    const data = await response.json() as any;
    if (!response.ok) throw new ApiError(response.status === 422 ? 422 : 503, data?.error?.message || data?.detail || 'AI service could not complete the request.');
    if (!data || typeof data !== 'object' || data.success === false) throw new ApiError(502,'Invalid AI response.');
    return data;
  } catch(error) {
    if(error instanceof ApiError) throw error;
    throw new ApiError(503,path==='/integration/assistant'?'The assistant is unavailable or timed out. Your message was not saved. Please try again.':'AI service is unavailable or timed out. Your referral is still saved.');
  }
}
