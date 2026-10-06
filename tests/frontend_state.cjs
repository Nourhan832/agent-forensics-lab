// Execute the real frontend against a small DOM/API double; no model calls.
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const catalogs = JSON.parse(fs.readFileSync(0, 'utf8'));
const elements = new Map();
function element(id = '') {
  return {id, textContent: '', innerHTML: '', disabled: false, hidden: false,
    style: {}, dataset: {}, listeners: {}, children: [], classList: {add(){}, remove(){}, toggle(){}},
    addEventListener(event, callback){this.listeners[event] = callback;},
    setAttribute(){}, scrollIntoView(){}, appendChild(child){this.children.push(child);}, click(){},
    querySelector(selector){return get(id + selector);}, querySelectorAll(){return [];}};
}
function get(id){if (!elements.has(id)) elements.set(id, element(id));return elements.get(id);}
const cards = Object.entries(catalogs).flatMap(([domain, categories]) => categories.map(c => {
  const card = get(c.id); card.dataset = {category:c.id, investigationDomain:domain}; return card;
}));
const domainButtons = ['customer_support', 'emergency_response'].map(domain => {
  const b=get(domain);b.dataset.domain=domain;return b;
});
const requests=[];
let nextResponse;
const context = vm.createContext({console:{error(){}}, URL, Blob, Set,
  setInterval(){return 1;},
  window:{location:{origin:'http://audit.local'}}, alert(){}, setTimeout(fn){fn();}, clearInterval(){},
  document: {getElementById:get, createElement:element,
    querySelector(selector){
      const match=selector.match(/^\[data-category="([^"]+)"\]$/);
      return match ? get(match[1]) : get(selector);
    }, querySelectorAll(selector){
      if(selector === '.investigation-card') return cards;
      if(selector === '.domain-button') return domainButtons;
      return [];
    }},
  fetch: async (url, options) => {
    requests.push({url, options});
    if(nextResponse){const r=nextResponse;nextResponse=undefined;return r;}
    let data = url.endsWith('/ready') ? {status:'ready'} : {success:true,regressions:[]};
    if(url.includes('/api/categories?domain=')) data={categories:catalogs[url.split('domain=')[1]]};
    return {ok:true,json:async()=>data};
  },
});
vm.runInContext(fs.readFileSync('frontend/app.js','utf8'),context);
const run=code=>vm.runInContext(code,context);
const response=data=>({ok:true,json:async()=>data});
function payload({reproduced=true, before=true, after=false, bc=true, ac=true, verified=true}={}) {
  const side=(failed,completed)=>({agent_result:{completed,final_response:'Recorded response'},events:[],violations:failed?[{violation:'UNAUTHORIZED_RESOURCE_DISPATCH'}]:[]});
  return {success:true,replay_id:'test-receipt',result:{before_fix:side(before,bc),after_fix:side(after,ac)},
    verification:{reproduced,before_failed:before,after_failed:after,completed:bc&&ac,mitigation_verified:verified,utility_success:true}};
}
async function main(){
  await new Promise(resolve=>setImmediate(resolve));
  const name=process.argv[2];
  if(['verified_customer','verified_emergency','not_reproduced','other_failure','protected_violation','incomplete_before','incomplete_after','contradictory_receipt','saved_replay'].includes(name)){
    run(`activeDomain='${name==='verified_customer'?'customer_support':'emergency_response'}'; activeCategory='emergency_dispatch'; regressionTest.textContent='status:\\n  pending_replay';`);
    let p=payload();
    if(name==='not_reproduced') p=payload({reproduced:false,before:false,verified:false});
    if(name==='other_failure') p=payload({reproduced:false,before:true,verified:false});
    if(name==='protected_violation') p=payload({after:true,verified:false});
    if(name==='incomplete_before') p=payload({bc:false,verified:false});
    if(name==='incomplete_after') p=payload({ac:false,verified:false});
    if(name==='contradictory_receipt') p=payload({after:true,verified:true});
    if(name==='saved_replay') run(`lastSavedRegressionId=3;regressionTest.textContent='status:\\n  saved';`);
    context.testPayload=p;run('renderReplayResult(testPayload)');
    const verified=name.startsWith('verified_');
    assert.equal(get('saveRegressionButton').disabled,!verified);
    assert.equal(get('confidenceMitigation').textContent,verified||name==='saved_replay'?'VERIFIED':'NOT VERIFIED');
    if(name==='not_reproduced'||name==='other_failure'){
      assert.equal(get('beforeReplayStatus').textContent,'NOT REPRODUCED');
      assert.match(get('beforeReplayMeta').textContent,/Mitigation cannot be verified/);
      assert.match(get('regressionTest').textContent,/not_reproduced/);
    } else if(name.startsWith('incomplete')){
      assert.equal(get('confidenceReplay').textContent,'INCOMPLETE');
      assert.match(get('regressionTest').textContent,/incomplete/);
    } else if(name==='protected_violation'||name==='contradictory_receipt'){
      assert.equal(get('afterReplayStatus').textContent,'VIOLATION REMAINS');
      assert.match(get('regressionTest').textContent,/not_verified/);
    } else if(verified) {
      assert.match(get('regressionTest').textContent,/verified/);
      assert.equal(get('beforeReplayStatus').textContent,'REPRODUCED');
      assert.equal(get('afterReplayStatus').textContent,'GUARDRAIL VERIFIED');
      assert.match(get('afterReplayMeta').textContent,/No policy violation observed in the protected replay/);
    }
    else if(name==='saved_replay') assert.match(get('regressionTest').textContent,/saved/);
  } else if(name==='eligibility') {
    for(const domain of ['customer_support','emergency_response']) {
      run(`activeDomain='${domain}'; activeCategory='emergency_dispatch'; lastResult={failed:false,category_failure_detected:false};`);
      assert.equal(run('canReplayInvestigation()'),false);
      run('lastResult={failed:true,category_failure_detected:false};');assert.equal(run('canReplayInvestigation()'),false);
      run('lastResult={failed:true,category_failure_detected:true};');assert.equal(run('canReplayInvestigation()'),true);
    }
  } else if(name==='severity') {
    for(const categories of Object.values(catalogs))for(const c of categories){
      assert.equal(get(c.id).querySelector('.category-severity').textContent,'Severity: '+c.severity);
    }
  } else if(name==='readiness') {
    assert.equal(get('runtimeStatus').textContent,'Ready');
    assert(requests.some(r=>r.url.endsWith('/ready')));assert(!requests.some(r=>r.url.endsWith('/health')));
    nextResponse={ok:false,json:async()=>({status:'unconfigured'})};await run('checkBackend()');
    assert.equal(get('runtimeStatus').textContent,'Not ready');
    nextResponse=response({status:'healthy'});await run('checkBackend()');assert.equal(get('runtimeStatus').textContent,'Not ready');
    await run('checkBackend()');assert.equal(get('runtimeStatus').textContent,'Ready');
  } else if(name==='export') {
    assert.equal(get('exportReportButton').disabled,true);
    run(`lastResult={attack:{user_message:'Task'},events:[],failed:false,category_failure_detected:false,agent_result:{completed:true,final_response:'Result'}};renderInvestigation(lastResult);`);
    assert.equal(get('exportReportButton').disabled,false);
    run('resetWorkspace()');assert.equal(get('exportReportButton').disabled,true);
  } else if(name==='last_run') {
    run(`renderRegressionSuite([{id:3,category:'cross_customer_data_access',before_violations:[],after_violations:[],created_at:'2026-10-04T00:00:00Z'}]);`);
    assert.equal(get('regressionSuiteList').children.length,1);
    assert(!get('regressionSuiteList').children[0].innerHTML.includes('Last run'));
    assert(get('regressionSuiteList').children[0].innerHTML.includes('regression-card-status unverified'));
  } else if(name==='load_error') {
    nextResponse={ok:false,status:429,json:async()=>({detail:'Retry after the rate limit window.'})};
    await run('loadRegressionSuite()');assert.equal(get('regressionSuiteCount').textContent,'ERROR');
    assert.match(get('regressionSuiteList').innerHTML,/could not be loaded/);
    await run('loadRegressionSuite()');assert.equal(get('regressionSuiteCount').textContent,'0 SAVED');
  } else if(name==='investigation_error') {
    nextResponse={ok:false,status:429,json:async()=>({detail:'Rate limited'})};
    await get('runInvestigationButton').listeners.click();
    assert.equal(get('workspaceStatus').textContent,'ERROR');assert.equal(get('runInvestigationButton').disabled,false);
    assert.equal(get('heroBlackboxStatus').textContent,'ERROR');assert.equal(get('replayButton').disabled,true);
    assert.equal(get('exportReportButton').disabled,true);assert.equal(get('saveRegressionButton').disabled,true);
  } else if(name==='replay_error') {
    run(`lastResult={failed:true,category_failure_detected:true,attack:{user_message:'Task'}};regressionTest.textContent='status:\\n  verified';`);
    nextResponse={ok:false,status:429,json:async()=>({detail:'Rate limited'})};
    await get('replayButton').listeners.click();
    assert.equal(get('beforeReplayStatus').textContent,'ERROR');assert.equal(get('afterReplayStatus').textContent,'ERROR');
    assert.equal(get('confidenceMitigation').textContent,'NOT VERIFIED');assert.equal(get('saveRegressionButton').disabled,true);
    assert.match(get('regressionTest').textContent,/replay_error/);assert.equal(get('replayButton').disabled,false);
  } else if(name==='replay_running') {
    run(`lastResult={failed:true,category_failure_detected:true,attack:{user_message:'Task'}};regressionTest.textContent='status:\\n  not_reproduced';`);
    let resume;nextResponse=new Promise(resolve=>resume=resolve);
    const pending=get('replayButton').listeners.click();
    await new Promise(resolve=>setImmediate(resolve));
    assert.equal(get('beforeReplayStatus').textContent,'RUNNING');
    assert.match(get('regressionTest').textContent,/replaying/);
    assert.equal(get('beforeReplayDetails').hidden,true);
    assert.equal(get('saveRegressionButton').disabled,true);
    resume(response(payload()));await pending;
    assert.equal(get('saveRegressionButton').disabled,false);
  } else if(name==='rerun_transient') {
    context.savedRegression={id:3,category:'cross_customer_data_access',minimal_trigger:'Task',mitigation_verified:true};
    context.testButton=get('testButton');context.testOutput=get('testOutput');
    for (const [status,detail] of [[409,'Another model workflow is running; retry after it completes'],[429,'Rate limited']]) {
      nextResponse={ok:false,status,json:async()=>({detail})};
      await run('rerunSavedRegression(savedRegression,testButton,testOutput)');
      assert.equal(context.savedRegression.mitigation_verified,true);
      assert.equal(get('testButton').textContent,'Rerun test');
      assert.match(get('testOutput').textContent,/Latest rerun: Not completed/);
      assert.match(get('testOutput').textContent,/Saved verification is unchanged/);
      assert.equal(get('testOutput').style.color,'var(--amber)');
    }
  } else if(name==='loading_copy') {
    run('showLoading()');
    assert.equal(get('loadingStage').textContent,'Analyzing agent behavior');
    assert.match(get('loadingMessage').textContent,/collecting trace evidence/);
    assert.equal(get('loadingElapsed').textContent,'Elapsed: 0s');
    assert.equal(get('loadingProgressBar').style.width,undefined);
    run('hideLoading()');
  } else if(name==='rerun_incomplete'||name==='rerun_not_reproduced') {
    nextResponse=response(name==='rerun_incomplete'?payload({ac:false,verified:false}):payload({reproduced:false,before:false,verified:false}));
    context.testButton=get('testButton');context.testOutput=get('testOutput');
    await run(`rerunSavedRegression({id:3,category:'cross_customer_data_access',minimal_trigger:'Task'},testButton,testOutput)`);
    assert.match(get('testOutput').textContent,name==='rerun_incomplete'?/INCOMPLETE/:/NOT REPRODUCED/);
    assert.equal(get('testButton').disabled,false);
  } else if(name==='save_error'||name==='save_running') {
    run(`lastResult={failed:true,category_failure_detected:true,primary_violation:{violation:'INDIRECT_PROMPT_INJECTION'},attack:{user_message:'Task'}};`);
    context.testPayload=payload();run('lastReplayResult=testPayload;');
    const errorResponse={ok:false,status:429,json:async()=>({detail:'Rate limited'})};
    let resume;
    nextResponse=name==='save_running'?new Promise(resolve=>resume=resolve):errorResponse;
    const pending=get('saveRegressionButton').listeners.click();
    if(name==='save_running'){
      await new Promise(resolve=>setImmediate(resolve));
      assert.equal(get('runInvestigationButton').disabled,true);
      assert.equal(get('replayButton').disabled,true);
      await get('emergency_response').listeners.click();assert.equal(run('activeDomain'),'customer_support');
      resume(errorResponse);
    }
    await pending;
    assert.equal(get('saveRegressionButton').disabled,false);assert.equal(get('runInvestigationButton').disabled,false);
    assert.equal(run('workflowBusy'),false);assert.equal(get('saveRegressionButton').textContent,'SAVE FAILED');
  } else throw Error('Unknown scenario '+name);
  console.log(name+' passed');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
