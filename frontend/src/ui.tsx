import {useState,type ReactNode} from 'react';
import {useQuery,useQueryClient} from '@tanstack/react-query';
import {useForm} from 'react-hook-form';
import {zodResolver} from '@hookform/resolvers/zod';
import {z} from 'zod';
import {get,post,api,errorMessage} from './api';
export function useData(path:string){return useQuery({queryKey:[path],queryFn:()=>get(path)});}
export function Status({query}:{query:{isPending:boolean;error:unknown}}){return query.isPending?<p className="notice" role="status">Loading records…</p>:query.error?<p className="error" role="alert">{errorMessage(query.error)}</p>:null;}
export function Badge({children}:{children:ReactNode}){return <span className="badge">{children}</span>;}
export function Empty({children='No records yet.'}:{children?:ReactNode}){return <div className="empty">{children}</div>;}
export function Heading({title,sub,action}:{title:string;sub:string;action?:ReactNode}){return <div className="page-heading"><div><p className="eyebrow">CONNECTED CARE / WORKSPACE</p><h1>{title}</h1><p>{sub}</p></div>{action}</div>;}
export type Field={name:string;label:string;type?:string;options?:string[];required?:boolean;min?:number;max?:number;value?:unknown};
export function Form({fields,onSubmit,label='Save changes',initial={}}:{fields:Field[];onSubmit:(v:any)=>Promise<unknown>;label?:string;initial?:Record<string,unknown>}){
  const shape:Record<string,z.ZodTypeAny>={};for(const f of fields){let s:z.ZodTypeAny=f.type==='number'?z.coerce.number().min(f.min??0).max(f.max??1000000):f.type==='checkbox'?z.boolean():f.type==='email'?z.string().email():f.type==='password'?z.string().min(12).max(128):z.string().min(f.required===false?0:1);if(f.required===false)s=s.optional();shape[f.name]=s;}
  const {register,handleSubmit,formState:{errors,isSubmitting},reset}=useForm({resolver:zodResolver(z.object(shape)),defaultValues:Object.fromEntries(fields.map(f=>[f.name,initial[f.name]??f.value??(f.type==='checkbox'?false:'')]))});
  const [message,setMessage]=useState(''),[error,setError]=useState('');const cache=useQueryClient();
  return <form className="form-grid" onSubmit={handleSubmit(async v=>{setError('');setMessage('');try{await onSubmit(v);setMessage('Saved successfully.');await cache.invalidateQueries();}catch(e){setError(errorMessage(e));}})}>
    {fields.map(f=><label className={f.type==='textarea'?'wide':''} key={f.name}>{f.label}{f.type==='select'?<select {...register(f.name)}><option value="">Select…</option>{f.options?.map(x=><option key={x}>{x}</option>)}</select>:f.type==='textarea'?<textarea rows={3} {...register(f.name)}/>:<input type={f.type||'text'} {...register(f.name)} min={f.min} max={f.max} step={['latitude','longitude'].includes(f.name)?'any':undefined} autoComplete={f.type==='password'?'new-password':undefined}/>} {errors[f.name]&&<small className="field-error">{String(errors[f.name]?.message)}</small>}</label>)}
    <div className="wide form-footer">{error&&<p className="error" role="alert">{error}</p>}{message&&<p className="success" role="status">{message}</p>}<button disabled={isSubmitting}>{isSubmitting?'Saving…':label}</button></div>
  </form>;
}
export function Action({path,body,children,method='POST',onDone}:{path:string;body?:unknown;children:ReactNode;method?:'POST'|'PATCH';onDone?:(data:any)=>void}){
  const [busy,setBusy]=useState(false),[error,setError]=useState('');const cache=useQueryClient();return <span className="action"><button className="secondary" disabled={busy} onClick={async()=>{setBusy(true);setError('');try{const data=method==='PATCH'?(await api.patch(path,body)).data:await post(path,body);onDone?.(data);await cache.invalidateQueries();}catch(e){setError(errorMessage(e));}finally{setBusy(false);}}}>{busy?'Working…':children}</button>{error&&<small className="field-error" role="alert">{error}</small>}</span>;
}
export const date=(s:string)=>new Date(s).toLocaleString();
