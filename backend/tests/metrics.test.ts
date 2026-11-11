import {test} from 'node:test';
import assert from 'node:assert/strict';
import {delayMetrics} from '../src/metrics.js';
test('empty and tiny samples never claim adequate evaluation',()=>{
  assert.equal(delayMetrics([]).accuracy,null);
  const result=delayMetrics([{predicted:1,actual:1},{predicted:1,actual:0},{predicted:0,actual:1}]);
  assert.equal(result.status,'insufficient_data');assert.equal(result.accuracy,1/3);assert.equal(result.recall,.5);assert.equal(result.f1,.5);
});
