import axios from 'axios';
export const api=axios.create({baseURL:import.meta.env.VITE_API_URL||'/api',withCredentials:true,timeout:25000});
let token:string|null=null;
let refresh:Promise<any>|null=null;
export function setToken(value:string|null){token=value;}
api.interceptors.request.use(c=>{if(token)c.headers.Authorization=`Bearer ${token}`;return c;});
api.interceptors.response.use(r=>r,async error=>{
  const c=error.config;
  if(error.response?.status===401&&c&&!c._retry&&!c.url.startsWith('/auth/')){
    c._retry=true;
    refresh??=api.post('/auth/refresh').then(r=>{setToken(r.data.accessToken);return r;}).finally(()=>{refresh=null;});
    try{await refresh;return api(c);}catch{setToken(null);window.dispatchEvent(new Event('session-expired'));}
  }throw error;
});
export const get=async(path:string)=>(await api.get(path)).data;
export const post=async(path:string,body?:unknown)=>(await api.post(path,body===undefined?{}:body,{headers:{'Content-Type':'application/json'}})).data;
export function errorMessage(e:unknown){return axios.isAxiosError(e)?e.response?.data?.error?.message||'Connection failed. Please try again.':e instanceof Error?e.message:'The request could not be completed.';}
