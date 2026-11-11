import {db} from './app.js';
export function delayMetrics(rows:{predicted:number;actual:number}[]){
  const tp=rows.filter(r=>r.predicted===1&&r.actual===1).length,tn=rows.filter(r=>r.predicted===0&&r.actual===0).length;
  const fp=rows.filter(r=>r.predicted===1&&r.actual===0).length,fn=rows.filter(r=>r.predicted===0&&r.actual===1).length;
  return {samples:rows.length,status:rows.length>=30&&tp+fn>=10&&tn+fp>=10?'observed':'insufficient_data',accuracy:rows.length?(tp+tn)/rows.length:null,precision:tp+fp?tp/(tp+fp):null,recall:tp+fn?tp/(tp+fn):null,f1:2*tp+fp+fn?2*tp/(2*tp+fp+fn):null,confusion:{truePositive:tp,trueNegative:tn,falsePositive:fp,falseNegative:fn}};
}
export async function intelligenceMetrics(hospitalId?:string){
  const predictions=await db.prediction.findMany({where:{hospitalId,createdAt:{gte:new Date(Date.now()-90*86400000)}},include:{referral:{include:{outcome:true}}},orderBy:{createdAt:'desc'},take:5000});
  const pairs: {predicted:number;actual:number}[]=[];const seen=new Set();let highRisk=0;const trend:Record<string,{date:string;predictions:number;highRisk:number}>={};
  for(const p of predictions){
    const data=p.result as any;const selected=data.ranked_hospitals?.find((x:any)=>x.hospital_id===p.referral?.destinationId);const delay=selected?.delay_prediction??(p.component==='delay'?data:null);const key=p.createdAt.toISOString().slice(0,10);trend[key]??={date:key,predictions:0,highRisk:0};trend[key].predictions++;
    if(delay?.delay_probability>=.5){highRisk++;trend[key].highRisk++;}
    if(delay&&p.referral?.outcome?.verifiedAt&&!seen.has(p.referralId)){seen.add(p.referralId);pairs.push({predicted:Number(delay.delay_probability>=.5),actual:Number(p.referral.outcome.actualDelayMinutes>120)});}
  }
  return {windowDays:90,boundedAt:5000,predictionCount:predictions.length,highRiskPredictions:highRisk,delay:delayMetrics(pairs),trends:Object.values(trend).sort((a,b)=>a.date.localeCompare(b.date)),modelVersions:[...new Set(predictions.map(p=>p.modelVersionId))],limitations:['Metrics use verified outcomes only. Missing predictions are excluded, not counted as correct.','Recommendation outcomes are observational; these metrics do not establish clinical benefit.']};
}
