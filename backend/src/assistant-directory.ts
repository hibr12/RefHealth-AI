type DirectoryHospital={id:string;name:string;status:string};

/** Build complete, bounded source documents from this request's authorized DB rows. */
export function assistantDirectory(hospitals:DirectoryHospital[],hospitalId:string){
  const approved=hospitals.filter(h=>h.status==='APPROVED').map(({id,name,status})=>({id,name,status}));
  const parts:DirectoryHospital[][]=[];
  let part:DirectoryHospital[]=[],size=0;
  for(const hospital of approved){
    const length=JSON.stringify(hospital).length+1;
    if(part.length&&size+length>20000){parts.push(part);part=[];size=0;}
    part.push(hospital);size+=length;
  }
  if(part.length||!parts.length)parts.push(part);
  const now=new Date().toISOString();
  return parts.map((entries,index)=>({
    id:`system:approved-hospital-directory:${index+1}`,hospital_id:hospitalId,category:'directory',
    source:'Live approved hospital directory',updated_at:now,review_at:null,
    content:JSON.stringify({
      as_of:now,scope:'All APPROVED hospitals visible in the hospital directory. Other registration statuses are excluded.',
      active_definition:'APPROVED means enabled in this system. It does not establish current opening hours, referral acceptance or bed availability.',
      approved_hospital_count:approved.length,part:index+1,total_parts:parts.length,hospitals:entries,
    }),
  }));
}
