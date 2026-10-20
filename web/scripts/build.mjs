import {readFileSync,writeFileSync,mkdirSync} from 'node:fs';
const ui=readFileSync('ui.html','utf8'),code=readFileSync('worker/service.js','utf8');
writeFileSync('worker/index.js','const APP='+JSON.stringify(ui)+';\n'+code);
mkdirSync('dist/server',{recursive:true});mkdirSync('dist/.openai',{recursive:true});
writeFileSync('dist/server/index.js',readFileSync('worker/index.js'));
writeFileSync('dist/.openai/hosting.json',readFileSync('.openai/hosting.json'));
