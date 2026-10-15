const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
async function scenario(status = true) {
 let ready, submit, config, resolveInit, uploaded = false, saved = false, sent = false, alert = null;
 const button = {disabled:false,textContent:'Save changes'};
 const form = {
   querySelector: s => s === 'button[type=submit]' ? button : s === '[name=csrfmiddlewaretoken]' ? {value:'csrf-test'} : null,
   contains: () => true, addEventListener: (event, fn) => {submit = fn;},
   requestSubmit: () => {throw new Error('Must not restart the submit event');},
   prepend: a => {alert = a;}
 };
 const document = {
   addEventListener: (event, fn) => {ready = fn;}, querySelectorAll: () => [1], querySelector: s => s === '.editor-form' ? form : null,
   createElement: () => ({setAttribute(){},scrollIntoView(){}})
 };
 const editor = {getElement:()=>({}),uploadImages:async()=>{uploaded = true;return [{status}];},getContent:()=>'<p>Saved</p>'};
 const tinymce = {init: c=>{config=c; return new Promise(resolve=>{resolveInit=resolve;});},get:()=>[editor],triggerSave:()=>{saved=true;}};
 let request;
 vm.runInNewContext(fs.readFileSync('static/js/editor.js','utf8'), {
   document,window:{tinymce},tinymce,FormData,
   HTMLFormElement: {prototype: {submit() {assert.equal(this,form); assert(uploaded); assert(saved); sent = true;}}},
   fetch: async (url, options) => {request={url,options};return {ok:true,json:async()=>({location:'/media/editor/test.jpg'})};}
 });
 ready();
 assert(config.plugins.includes('image'));
 const result = await config.images_upload_handler({blob:()=>new Blob(['test']),filename:()=> 'test.png'});
 assert.equal(result,'/media/editor/test.jpg');
 assert.equal(request.options.headers['X-CSRFToken'],'csrf-test');
 assert.equal(request.options.credentials,'same-origin');
 const saving = submit({preventDefault(){}});
 assert.equal(uploaded,false,'Wait for editor initialization before saving');
 resolveInit();
 await saving;
 assert.equal(sent,status);
 assert.equal(button.disabled,status);
 if (status) { sent = false; await submit({preventDefault(){}}); assert.equal(sent,false, 'Ignore duplicate clicks while saving'); }
 if (!status) assert(alert.textContent.includes('could not be uploaded'));
}
async function pickerScenario(ok = true, cancelled = false) {
 let ready, config, change, clicked = false, callbackUrl = null, notice = null, request;
 const progress = [];
 const file = new Blob(['image'], {type:'image/png'});
 const input = {files:cancelled ? [] : [file], addEventListener(event,fn){change=fn;},click(){clicked=true;}};
 const editor = {setProgressState:value=>progress.push(value),notificationManager:{open:value=>{notice=value;}}};
 const form = {querySelector:()=>({value:'csrf-token'}),addEventListener(){}};
 const document = {addEventListener(event,fn){ready=fn;},querySelectorAll:()=>[1],
   querySelector:selector=>selector==='.editor-form'?form:null,createElement:()=>input};
 const tinymce = {activeEditor:editor,init:options=>{config=options;return Promise.resolve([]);}};
 vm.runInNewContext(fs.readFileSync('static/js/editor.js','utf8'),{document,window:{tinymce},tinymce,FormData,
   fetch:async(url,options)=>{request={url,options};return {ok,json:async()=>ok?{location:'/media/editor/picked.jpg'}:{error:'Image upload rejected.'}};}});
 ready();
 config.file_picker_callback(url=>{callbackUrl=url;},'',{filetype:'image'});
 assert(clicked);
 assert.equal(input.accept,'image/jpeg,image/png,image/webp');
 await change();
 if(cancelled){assert.equal(request,undefined);assert.equal(progress.length,0);return;}
 assert.deepEqual(progress,[true,false]);
 assert.equal(request.options.headers['X-CSRFToken'],'csrf-token');
 if(ok) assert.equal(callbackUrl,'/media/editor/picked.jpg');
 else {assert.equal(callbackUrl,null);assert.equal(notice.type,'error');assert.equal(notice.text,'Image upload rejected.');}
}
(async()=>{await scenario(true);await scenario(false);await pickerScenario();await pickerScenario(false);await pickerScenario(true,true);console.log('Editor image picker, upload and save checks passed.');})().catch(e=>{console.error(e);process.exitCode=1;});
