import {createContext,useContext,useEffect,useState,type ReactNode} from 'react';
import {api,post,setToken} from './api';
import {useQueryClient} from '@tanstack/react-query';
export type User={id:string;name:string;email:string;role:'SYSTEM_ADMIN'|'HOSPITAL_ADMIN'|'HEALTHCARE_WORKER';hospitalId:string|null;permissions?:string[]};
const Auth=createContext<{user:User|null;loading:boolean;login:(email:string,password:string)=>Promise<void>;logout:()=>Promise<void>}>({user:null,loading:true,login:async()=>{},logout:async()=>{}});
export function AuthProvider({children}:{children:ReactNode}){
  const [user,setUser]=useState<User|null>(null),[loading,setLoading]=useState(true);const cache=useQueryClient();
  useEffect(()=>{let active=true;post('/auth/refresh').then(data=>{if(active){setToken(data.accessToken);setUser(data.user);}}).catch(()=>{}).finally(()=>{if(active)setLoading(false);});const expired=()=>{setUser(null);cache.clear();};window.addEventListener('session-expired',expired);return()=>{active=false;window.removeEventListener('session-expired',expired);};},[cache]);
  async function login(email:string,password:string){const data=await post('/auth/login',{email,password});setToken(data.accessToken);const me=(await api.get('/auth/me')).data;cache.clear();setUser(me.user);}
  async function logout(){try{await post('/auth/logout');}finally{setToken(null);setUser(null);cache.clear();}}
  return <Auth.Provider value={{user,loading,login,logout}}>{children}</Auth.Provider>;
}
export const useAuth=()=>useContext(Auth);
