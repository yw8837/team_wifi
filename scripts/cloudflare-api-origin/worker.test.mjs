import {test} from 'node:test';
import assert from 'node:assert/strict';
import {routeRecoveryApi} from './worker.mjs';

const home = 'https://moduyuga.yeolmaeapps.kr';
const api = 'https://moduyuga-api.yeolmaeapps.kr/api';
const list = api + '/release/groupbuys?status=active&limit=5';
const request = (url=list, options={}) => new Request(url,options);

test('full recovery sends a write once to the fixed API and never forwards unrelated cookies',async()=>{
  const req=request(api+'/release/test',{method:'POST',headers:{authorization:'Bearer test',cookie:'other=1',origin:home,'x-forwarded-host':'invalid'},body:'payload'});
  let calls=0;
  const response=await routeRecoveryApi(req,async(target,init)=>{
    calls++;assert.equal(target.href,'https://moduyuga-beta.onrender.com/api/release/test');
    assert.equal(init.redirect,'manual');assert.equal(init.method,'POST');
    assert.equal(init.headers.get('authorization'),'Bearer test');
    assert.equal(init.headers.get('cookie'),null);
    assert.equal(init.headers.get('x-forwarded-host'),null);
    assert.equal(await new Response(init.body).text(),'payload');
    throw Error('network');
  });
  assert.equal(calls,1);assert.equal(response.status,503);
});

test('public reads keep the exact path and query and use the origin response as-is',async()=>{
  const expected=Response.json({items:[{id:'item'}]});
  assert.equal(await routeRecoveryApi(request(list),async(target,init)=>{
    assert.equal(target.search,'?status=active&limit=5');
    assert.equal(target.pathname,'/api/release/groupbuys');
    assert.equal(init.method,'GET');
    return expected;
  }),expected);
});

test('redirects stay visible to OAuth clients and preflight goes to the same backend',async()=>{
  const expected=new Response(null,{status:302,headers:{Location:home+'/auth/complete'}});
  assert.equal(await routeRecoveryApi(request(api+'/auth/social/kakao/callback'),async(_,init)=>{
    assert.equal(init.redirect,'manual');return expected;
  }),expected);
  await routeRecoveryApi(request(list,{method:'OPTIONS',headers:{Origin:home,'Access-Control-Request-Method':'GET'}}),async(_,init)=>{
    assert.equal(init.headers.get('origin'),home);
    assert.equal(init.headers.get('access-control-request-method'),'GET');
    return new Response(null,{status:204});
  });
});

test('rejects other hosts and paths without forwarding',async()=>{
  for(const address of ['https://other.example/api/health','https://moduyuga-api.yeolmaeapps.kr/']) {
    assert.equal((await routeRecoveryApi(request(address),()=>assert.fail('unexpected request'))).status,404);
  }
});
