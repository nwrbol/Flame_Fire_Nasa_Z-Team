const {assess,describe}=require('./engine.js');const fs=require('fs');
const html=fs.readFileSync('/home/claude/out/firegap_assistant.html','utf8');
const m=html.match(/const DATA = (\{.*\});\n/);const DATA=JSON.parse(m[1]);
for(const [o,p] of [[21,101.3],[26.5,70.3],[34,56.5],[30,50],[21,60],[26,200],[45,100]]){
  const a=assess(DATA,o,p);console.log(`\n== ${o}% ${p} kPa -> verdict ${a.verdict}`);
  for(const f of a.families)console.log(' ',f.fam,f.level,'close',f.nClose,'near',f.nNear,JSON.stringify(f.counts),f.classified);
  const e=a.families.find(f=>f.examples.length&&f.nClose); if(e)console.log('  ex:',describe(e.examples[0]));
}
