const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
function scenario(isMobile, remembered = false) {
  let ready, keydown, resize;
  const classes = new Set();
  const listeners = new Map();
  const store = new Map([['staff-navigation-hidden', String(remembered)]]);
  const button = () => ({attributes: {}, addEventListener(e, fn) {listeners.set(this, fn);}, setAttribute(k,v) {this.attributes[k]=v;}, focus() {document.activeElement=this;}});
  const toggle = button(), close = button(), last = button(), backdrop = button();
  const sidebar = {setAttribute(){}, querySelector: () => close, querySelectorAll: () => [close,last], contains: item => [close,last].includes(item)};
  const mobile = {matches:isMobile, addEventListener(e,fn) {resize=fn;}};
  const document = {
    body: {classList: {add(c) {classes.add(c);}, toggle(c,v) {v ? classes.add(c) : classes.delete(c);}}},
    addEventListener(e,fn) {if(e==='DOMContentLoaded') ready=fn; else keydown=fn;},
    querySelector(s) {return s==='#staff-navigation' ? sidebar : s==='[data-staff-nav-toggle]' ? toggle : backdrop;},
    querySelectorAll: () => [close,backdrop],
  };
  vm.runInNewContext(fs.readFileSync('static/js/staff-nav.js','utf8'), {document,window:{matchMedia:()=>mobile},localStorage:{getItem:k=>store.get(k),setItem:(k,v)=>store.set(k,v)}});
  ready();
  assert.equal(toggle.attributes['aria-expanded'], String(!isMobile && !remembered));
  if (isMobile || remembered) listeners.get(toggle)();
  assert.equal(sidebar.inert,false);
  if (isMobile) {
    assert.equal(document.activeElement,close);
    assert.equal(backdrop.hidden,false);
    document.activeElement=last;
    let prevented=false;
    keydown({key:'Tab',preventDefault(){prevented=true;}});
    assert(prevented); assert.equal(document.activeElement,close);
    keydown({key:'Escape'});
    assert.equal(sidebar.inert,true); assert.equal(document.activeElement,toggle);
    assert.equal(backdrop.hidden,true);
  } else {
    listeners.get(close)();
    assert.equal(store.get('staff-navigation-hidden'),'true');
    assert.equal(sidebar.inert,true);
    listeners.get(toggle)();
    assert.equal(store.get('staff-navigation-hidden'),'false');
    mobile.matches=true; resize();
    assert.equal(sidebar.inert,true);
    mobile.matches=false; resize();
    assert.equal(sidebar.inert,false);
  }
}
scenario(false);scenario(false,true);scenario(true);
console.log('Staff navigation desktop/mobile, keyboard and persistence checks passed.');
