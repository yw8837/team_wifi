import assert from 'node:assert/strict';
import {test} from 'node:test';
import {catalogueSnapshot} from './public-catalogue-snapshot.mjs';
import {checkPublicProduct} from './search-index-worker/worker.mjs';

test('only reviewed seller listings contribute public fields to the snapshot', () => {
 const row = {id:'p', title:'상품', seller_name:'판매처', seller_url:'https://www.aguardmall.com/product/detail.html?product_no=1509',
   source_checked_at:'2026-11-23T10:00:00Z', source_fresh_until:'2026-11-24T10:00:00Z',
   author:{id:'private'},saved:true, status:'active',review_state:'clear',source_type:'seller_page'};
 const rows = [row, ...[{status:'ended'}, {is_demo:true}, {review_state:'needs_review'}, {seller_url:'https://example.org'},
   {source_type:'member'}, {source_checked_at:'bad'}].map(change=>({...row,...change}))];
 assert.deepEqual(catalogueSnapshot(rows),[{id:'p',title:'상품',seller:'판매처',url:row.seller_url,checked:row.source_checked_at,expires:row.source_fresh_until}]);
});

test('external check records a real detail page and detects both a gateway failure and an empty app shell', async t=>{
 const id='443f26bb-e66e-489d-a431-22ad0b4216df';
 const url='https://moduyuga.yeolmaeapps.kr/groupbuys/'+id+'/public';
 let response=new Response('<h1>상품</h1><a href="https://example.kr">판매처에서 현재 조건 확인</a>');
 t.mock.method(globalThis,'fetch',async path=>path===url?response:new Response('<url><loc>'+url+'</loc></url>'));
 let state;
 const env={STATE:{put:async(_,value)=>{state=JSON.parse(value)}}};
 await checkPublicProduct(env);assert.equal(state.ok,true);
 for (response of [new Response('<div id="root"></div>'),new Response('',{status:530})]){
   await assert.rejects(checkPublicProduct(env));assert.equal(state.ok,false);
 }
});
