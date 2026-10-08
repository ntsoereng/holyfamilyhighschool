const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
async function scenario(status = true) {
 let ready, submit, config, uploaded = false, saved = false, sent = false, alert = null;
 const button = {disabled:false,textContent:'Save changes'};
 const form = {
   querySelector: s => s === 'button[type=submit]' ? button : s === '[name=csrfmiddlewaretoken]' ? {value:'csrf-test'} : null,
   contains: () => true, addEventListener: (event, fn) => {submit = fn;},
   requestSubmit: () => {assert(uploaded); assert(saved); assert(!button.disabled); sent = true;},
   prepend: a => {alert = a;}
 };
 const document = {
   addEventListener: (event, fn) => {ready = fn;}, querySelectorAll: () => [1], querySelector: () => form,
   createElement: () => ({setAttribute(){},scrollIntoView(){}})
 };
 const editor = {getElement:()=>({}),uploadImages:async()=>{uploaded = true;return [{status}];},getContent:()=>'<p>Saved</p>'};
 const tinymce = {init: c=>{config=c;},get:()=>[editor],triggerSave:()=>{saved=true;}};
 let request;
 vm.runInNewContext(fs.readFileSync('static/js/editor.js','utf8'), {
   document,window:{tinymce},tinymce,FormData,
   fetch: async (url, options) => {request={url,options};return {ok:true,json:async()=>({location:'/media/editor/test.jpg'})};}
 });
 ready();
 assert(config.plugins.includes('image'));
 const result = await config.images_upload_handler({blob:()=>new Blob(['test']),filename:()=> 'test.png'});
 assert.equal(result,'/media/editor/test.jpg');
 assert.equal(request.options.headers['X-CSRFToken'],'csrf-test');
 assert.equal(request.options.credentials,'same-origin');
 await submit({preventDefault(){}});
 assert.equal(sent,status);
 assert.equal(button.disabled,false);
 if (!status) assert(alert.textContent.includes('could not be uploaded'));
}
(async()=>{await scenario(true);await scenario(false);console.log('Editor upload/save checks passed.');})().catch(e=>{console.error(e);process.exitCode=1;});
