import {test} from 'node:test';
import assert from 'node:assert/strict';
import {assistantDirectory} from '../src/assistant-directory.js';

test('directory counts and lists only approved hospitals without private profile fields',()=>{
  const hospitals=[
    {id:'approved',name:'Approved Hospital',status:'APPROVED',capacity:{availableBeds:9},email:'private@example.org'},
    {id:'pending',name:'Pending Hospital',status:'PENDING'},
    {id:'suspended',name:'Suspended Hospital',status:'SUSPENDED'},
    {id:'rejected',name:'Rejected Hospital',status:'REJECTED'},
  ];
  const documents=assistantDirectory(hospitals,'requesting-hospital');
  assert.equal(documents.length,1);
  const directory=JSON.parse(documents[0].content);
  assert.equal(directory.approved_hospital_count,1);
  assert.deepEqual(directory.hospitals,[{id:'approved',name:'Approved Hospital',status:'APPROVED'}]);
  assert.match(directory.active_definition,/does not establish/);
  assert.ok(!documents[0].content.includes('private@example.org'));
  assert.ok(!documents[0].content.includes('availableBeds'));
  hospitals[0].status='SUSPENDED';
  const current=JSON.parse(assistantDirectory(hospitals,'requesting-hospital')[0].content);
  assert.equal(current.approved_hospital_count,0);
  assert.deepEqual(current.hospitals,[]);
});

test('large directories retain every hospital in bounded source documents',()=>{
  const hospitals=Array.from({length:250},(_,i)=>({id:`hospital-${i}`,name:`Hospital ${i} `+'x'.repeat(175),status:'APPROVED'}));
  const documents=assistantDirectory(hospitals,'requesting-hospital');
  assert.ok(documents.length>1);
  const parts=documents.map(document=>{
    assert.ok(document.content.length<=30000);
    const part=JSON.parse(document.content);
    assert.equal(part.approved_hospital_count,250);
    assert.equal(part.total_parts,documents.length);
    return part;
  });
  assert.deepEqual(parts.flatMap(part=>part.hospitals),hospitals);
});
