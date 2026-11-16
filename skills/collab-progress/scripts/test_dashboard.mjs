// Optional development checks; the skill runtime itself remains Python stdlib-only.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const page=fs.readFileSync(new URL('../assets/dashboard.html',import.meta.url),'utf8');
const source=fs.readFileSync(new URL('../assets/dashboard.js',import.meta.url),'utf8');
assert.ok(!page.includes('PROGRESS_DATA'),'The page template must not carry statistics');
assert.deepEqual([...page.matchAll(/<script src="([^"]+)"/g)].map(m=>m[1]),['dashboard-data.js','dashboard.js']);
const weekly=source.slice(source.indexOf('function calendarWeeks('),source.indexOf('function openTrait('));
const markdown=source.slice(source.indexOf('function inlineMarkdown('),source.indexOf('function openReport('));
const context=vm.createContext({scope:'all',current:{scopes:{all:{cumulative:{weekly_traits:{
  '2026-09-28':{T01:{eligible:3,applied:3,declined:0}},
  '2026-10-12':{T01:{eligible:3,applied:2,declined:0}}
}}}}},rate:c=>c&&c.eligible>=3&&(c.eligible-c.declined)>0?c.applied/(c.eligible-c.declined):null,
escapeText:s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))});
vm.runInContext(weekly+markdown,context);
const chart=vm.runInContext("weeklyChart('T01')",context);
assert.equal((chart.match(/<polyline /g)||[]).length,2,'An absent week must break the line');
assert.equal(vm.runInContext('calendarWeeks(current.scopes.all.cumulative.weekly_traits).length',context),3);
const report=vm.runInContext('markdownView("# Saved report\\n\\n| Name | Rate |\\n|---|---|\\n| <img src=x onerror=alert(1)> | 75% |")',context);
assert.ok(report.includes('&lt;img'));
assert.ok(!report.includes('<img'));
assert.equal((report.match(/<th>/g)||[]).length,2);
assert.equal((report.match(/<td>/g)||[]).length,2);
const themeSource=page.match(/<script id="theme-init">([\s\S]*?)<\/script>/)[1];
function themeHarness({saved=null,dark=false,blocked=false,legacy=false,noMedia=false}={}){
  const values=new Map(saved===null?[]:[['collab-progress-theme',saved]]),listeners=[];
  const inputs=['auto','light','dark'].map(value=>({value,checked:false,addEventListener(type,fn){this.changed=fn;}}));
  const media={matches:dark};
  media[legacy?'addListener':'addEventListener']=legacy?fn=>listeners.push(fn):(type,fn)=>listeners.push(fn);
  const document={documentElement:{dataset:{},style:{}},querySelectorAll:()=>inputs};
  const window={matchMedia(){if(noMedia)throw Error('unsupported');return media;}};
  const localStorage={getItem(key){if(blocked)throw Error('blocked');return values.get(key)??null;},setItem(key,value){if(blocked)throw Error('blocked');values.set(key,value);}};
  vm.runInNewContext(themeSource,{window,document,localStorage});
  window.progressTheme.bind();
  return {document,values,inputs,
    select(value){const input=inputs.find(i=>i.value===value);inputs.forEach(i=>i.checked=i===input);input.changed();},
    system(dark){media.matches=dark;listeners.forEach(fn=>fn());},
    get theme(){return document.documentElement.dataset.theme;}
  };
}
const auto=themeHarness({dark:true});
assert.equal(auto.theme,'dark','Auto uses the system before UI binding');
assert.ok(auto.inputs[0].checked);
auto.system(false);assert.equal(auto.theme,'light','Auto follows live system changes');
auto.select('dark');assert.equal(auto.theme,'dark');
auto.system(false);assert.equal(auto.theme,'dark','Explicit choice overrides system');
assert.equal(auto.values.get('collab-progress-theme'),'dark');
const reopened=themeHarness({saved:auto.values.get('collab-progress-theme'),dark:false});
assert.equal(reopened.theme,'dark','Reload restores saved choice');
assert.ok(reopened.inputs[2].checked);
reopened.select('light');reopened.system(true);assert.equal(reopened.theme,'light');
reopened.select('auto');assert.equal(reopened.theme,'dark');
assert.equal(reopened.values.get('collab-progress-theme'),'auto');
const blocked=themeHarness({blocked:true});
blocked.select('dark');assert.equal(blocked.theme,'dark','Blocked storage does not break switching');
assert.equal(blocked.document.documentElement.style.colorScheme,'dark');
assert.equal(themeHarness({saved:'unexpected',dark:true}).theme,'dark','Invalid saved preference defaults to Auto');
const legacy=themeHarness({legacy:true});legacy.system(true);assert.equal(legacy.theme,'dark');
const noMedia=themeHarness({noMedia:true});noMedia.select('dark');assert.equal(noMedia.theme,'dark');
const families={Direction:['T01','T02','T05','T06'],Context:['T04','T09','T10','T11','T12'],Ground:['T03','T07','T13','T14'],Orchestration:['T15','T16','T17','T19','T20'],Proof:['T08','T18','T21','T22','T23','T24']};
const artContext=vm.createContext({traitGroup:id=>Object.keys(families).find(f=>families[f].includes(id))});
vm.runInContext(source.slice(source.indexOf('const CATEGORY_ART ='),source.indexOf('function deltaHtml(')),artContext);
const art=vm.runInContext('({traits:TRAIT_ART,categories:CATEGORY_ART})',artContext);
assert.deepEqual(Object.keys(art.traits).sort(),Array.from({length:24},(_,i)=>'T'+String(i+1).padStart(2,'0')),'Every rubric trait needs explicit artwork');
assert.equal(new Set(Object.values(art.traits).map(a=>a.symbol)).size,24,'Every trait needs a distinct symbol name');
assert.equal(new Set(Object.values(art.traits).map(a=>a.body.replace(/\s+/g,' '))).size,24,'Central drawings must not repeat behind different labels');
assert.equal(new Set(Object.values(art.categories).map(a=>a.frame)).size,5,'Each category has a distinct family frame');
for(const [family,ids] of Object.entries(families)){
  assert.ok(vm.runInContext(`categoryIcon(${JSON.stringify(family)})`,artContext).includes('<svg'));
  for(const id of ids){
    const svg=vm.runInContext(`crest(${JSON.stringify(id)})`,artContext);
    assert.ok(svg.includes(`data-family="${family}"`));
    assert.ok(svg.includes(art.traits[id].body));
    assert.ok(svg.includes(art.categories[family].frame));
    assert.ok(!/<script|<image|href=|url\(/i.test(svg),'Artwork must stay self-contained');
  }
}
assert.throws(()=>vm.runInContext("crest('T99')",artContext),/Missing trait artwork/,'New traits must not silently reuse an icon');
console.log('Dashboard checks passed: missing-week gap, escaped reports, theme lifecycle, and 24 unique trait symbols across five families.');
