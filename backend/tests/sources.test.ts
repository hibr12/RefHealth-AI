import {test} from 'node:test';
import assert from 'node:assert/strict';
import {publicIPv4,collectPublicText} from '../src/sources.js';
test('public source fetch blocks private networks and invalid schemes',async()=>{
  for(const ip of ['127.0.0.1','10.0.0.1','172.16.0.1','192.168.1.1','169.254.169.254','0.0.0.0','100.64.0.1','::1','224.1.1.1'])assert.equal(publicIPv4(ip),false,ip);
  assert.equal(publicIPv4('8.8.8.8'),true);
  await assert.rejects(()=>collectPublicText('http://example.org'));
  await assert.rejects(()=>collectPublicText('https://user:password@example.org'));
  await assert.rejects(()=>collectPublicText('https://example.org:8443'));
});
