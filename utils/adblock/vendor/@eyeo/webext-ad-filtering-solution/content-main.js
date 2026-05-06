/******/ (() => { // webpackBootstrap
/******/ 	"use strict";

;// ../../node_modules/uuid/dist/esm-browser/native.js
const randomUUID = typeof crypto !== 'undefined' && crypto.randomUUID && crypto.randomUUID.bind(crypto);
/* harmony default export */ const esm_browser_native = ({
  randomUUID
});
;// ../../node_modules/uuid/dist/esm-browser/rng.js
// Unique ID creation requires a high quality random # generator. In the browser we therefore
// require the crypto API and do not support built-in fallback to lower quality random number
// generators (like Math.random()).
let getRandomValues;
const rnds8 = new Uint8Array(16);
function rng() {
  // lazy load so that environments that need to polyfill have a chance to do so
  if (!getRandomValues) {
    // getRandomValues needs to be invoked in a context where "this" is a Crypto implementation.
    getRandomValues = typeof crypto !== 'undefined' && crypto.getRandomValues && crypto.getRandomValues.bind(crypto);

    if (!getRandomValues) {
      throw new Error('crypto.getRandomValues() not supported. See https://github.com/uuidjs/uuid#getrandomvalues-not-supported');
    }
  }

  return getRandomValues(rnds8);
}
;// ../../node_modules/uuid/dist/esm-browser/stringify.js

/**
 * Convert array of 16 byte values to UUID string format of the form:
 * XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX
 */

const byteToHex = [];

for (let i = 0; i < 256; ++i) {
  byteToHex.push((i + 0x100).toString(16).slice(1));
}

function unsafeStringify(arr, offset = 0) {
  // Note: Be careful editing this code!  It's been tuned for performance
  // and works in ways you may not expect. See https://github.com/uuidjs/uuid/pull/434
  return byteToHex[arr[offset + 0]] + byteToHex[arr[offset + 1]] + byteToHex[arr[offset + 2]] + byteToHex[arr[offset + 3]] + '-' + byteToHex[arr[offset + 4]] + byteToHex[arr[offset + 5]] + '-' + byteToHex[arr[offset + 6]] + byteToHex[arr[offset + 7]] + '-' + byteToHex[arr[offset + 8]] + byteToHex[arr[offset + 9]] + '-' + byteToHex[arr[offset + 10]] + byteToHex[arr[offset + 11]] + byteToHex[arr[offset + 12]] + byteToHex[arr[offset + 13]] + byteToHex[arr[offset + 14]] + byteToHex[arr[offset + 15]];
}

function stringify(arr, offset = 0) {
  const uuid = unsafeStringify(arr, offset); // Consistency check for valid UUID.  If this throws, it's likely due to one
  // of the following:
  // - One or more input array values don't map to a hex octet (leading to
  // "undefined" in the uuid)
  // - Invalid input values for the RFC `version` or `variant` fields

  if (!validate(uuid)) {
    throw TypeError('Stringified UUID is invalid');
  }

  return uuid;
}

/* harmony default export */ const esm_browser_stringify = ((/* unused pure expression or super */ null && (stringify)));
;// ../../node_modules/uuid/dist/esm-browser/v4.js




function v4(options, buf, offset) {
  if (esm_browser_native.randomUUID && !buf && !options) {
    return esm_browser_native.randomUUID();
  }

  options = options || {};
  const rnds = options.random || (options.rng || rng)(); // Per 4.4, set bits for version and `clock_seq_hi_and_reserved`

  rnds[6] = rnds[6] & 0x0f | 0x40;
  rnds[8] = rnds[8] & 0x3f | 0x80; // Copy bytes to buffer, if provided

  if (buf) {
    offset = offset || 0;

    for (let i = 0; i < 16; ++i) {
      buf[offset + i] = rnds[i];
    }

    return buf;
  }

  return unsafeStringify(rnds);
}

/* harmony default export */ const esm_browser_v4 = (v4);
;// ../../node_modules/@eyeo/snippets/webext/main.mjs
/*!
 * This file is part of eyeo's Anti-Circumvention Snippets module (@eyeo/snippets),
 * Copyright (C) 2006-present eyeo GmbH
 * 
 * @eyeo/snippets is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 3 as
 * published by the Free Software Foundation.
 * 
 * @eyeo/snippets is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 * 
 * You should have received a copy of the GNU General Public License
 * along with @eyeo/snippets.  If not, see <http://www.gnu.org/licenses/>.
 */

let currentEnvironment = {initial: true};
const callback = (environment, ...filters) => {
const e=Proxy,{apply:t,bind:r,call:n}=Function,o=n.bind(t),s=n.bind(r),i=n.bind(n),a={get:(e,t)=>s(n,e[t])},c=t=>new e(t,a),l=(t,r)=>new e(t,{apply:(e,t,n)=>o(r,t,n)}),p={get:(e,t)=>s(e[t],e)},u=t=>new e(t,p),{assign:f,defineProperties:d,freeze:h,getOwnPropertyDescriptor:g,getOwnPropertyDescriptors:y,getPrototypeOf:w}=u(Object),{hasOwnProperty:m}=c({}),{species:v}=Symbol,b={get(e,t){const r=e[t];class n extends r{}const o=y(r.prototype);delete o.constructor,h(d(n.prototype,o));const s=y(r);return delete s.length,delete s.prototype,s[v]={value:n},h(d(n,s))}},E=t=>new e(t,b);"undefined"!=typeof currentEnvironment&&currentEnvironment.initial&&"undefined"!=typeof environment&&(currentEnvironment=environment);const S=()=>"undefined"!=typeof currentEnvironment?currentEnvironment:"undefined"!=typeof environment?environment:{};"undefined"==typeof globalThis&&(window.globalThis=window);const{apply:$,ownKeys:j}=u(Reflect),T=S(),x="world"in T,R=x&&"ISOLATED"===T.world,k=x&&"MAIN"===T.world,P="object"==typeof chrome&&!!chrome.runtime,A="object"==typeof browser&&!!browser.runtime,O=!k&&(R||P||A),L=e=>O?e:M(e,F(e)),{create:M,defineProperties:N,defineProperty:I,freeze:C,getOwnPropertyDescriptor:W,getOwnPropertyDescriptors:F}=u(Object),D=u(globalThis),H=O?globalThis:E(globalThis),{Map:q,RegExp:J,Set:B,WeakMap:z,WeakSet:_}=H,X=(e,t,r=null)=>{const n=j(t);for(const o of j(e)){if(n.includes(o))continue;const s=W(e,o);if(r&&"value"in s){const{value:e}=s;"function"==typeof e&&(s.value=r(e))}I(t,o,s)}},U=e=>{const t=H[e];class r extends t{}const{toString:n,valueOf:o}=t.prototype;N(r.prototype,{toString:{value:n},valueOf:{value:o}});const s=e.toLowerCase(),i=e=>function(){const t=$(e,this,arguments);return typeof t===s?new r(t):t};return X(t,r,i),X(t.prototype,r.prototype,i),r},V=C({frozen:new z,hidden:new _,iframePropertiesToAbort:{read:new B,write:new B},abortedIframes:new z}),G=new J("^[A-Z]"),K=O&&(P&&chrome||A&&browser)||void 0;var Q=new Proxy(new q([["chrome",K],["browser",K],["isExtensionContext",O],["variables",V],["console",L(console)],["document",globalThis.document],["JSON",L(JSON)],["Map",q],["Math",L(Math)],["Number",O?Number:U("Number")],["RegExp",J],["Set",B],["String",O?String:U("String")],["WeakMap",z],["WeakSet",_],["MouseEvent",MouseEvent]]),{get(e,t){if(e.has(t))return e.get(t);let r=globalThis[t];return"function"==typeof r&&(r=(G.test(t)?H:D)[t]),e.set(t,r),r},has:(e,t)=>e.has(t)});const Y={WeakSet:WeakSet,WeakMap:WeakMap,WeakValue:class{has(){return!1}set(){}}},{apply:Z}=Reflect;const{Map:ee,WeakMap:te,WeakSet:re,setTimeout:ne}=Q;let oe=!0,se=e=>{e.clear(),oe=!oe};var ie=function(e){const{WeakSet:t,WeakMap:r,WeakValue:n}=this||Y,o=new t,s=new r,i=new n;return function(t){if(o.has(t))return t;if(s.has(t))return s.get(t);if(i.has(t))return i.get(t);const r=Z(e,this,arguments);return o.add(r),r!==t&&("object"==typeof t&&t?s:i).set(t,r),r}}.bind({WeakMap:te,WeakSet:re,WeakValue:class extends ee{set(e,t){return oe&&(oe=!oe,ne(se,0,this)),super.set(e,t)}}});const{concat:ae,includes:ce,join:le,reduce:pe,unshift:ue}=c([]),fe=E(globalThis),{Map:de,WeakMap:he}=fe,ge=new de,ye=t=>{const r=(e=>{const t=[];let r=e;for(;r;){if(ge.has(r))ue(t,ge.get(r));else{const e=y(r);ge.set(r,e),ue(t,e)}r=w(r)}return ue(t,{}),o(f,null,t)})("function"==typeof t?t.prototype:t),n={get(e,t){if(t in r){const{value:n,get:o}=r[t];if(o)return i(o,e);if("function"==typeof n)return s(n,e)}return e[t]},set(e,t,n){if(t in r){const{set:o}=r[t];if(o)return i(o,e,n),!0}return e[t]=n,!0}};return t=>new e(t,n)},{isExtensionContext:we,Array:me,Number:ve,String:be,Object:Ee}=Q,{isArray:Se}=me,{getOwnPropertyDescriptor:$e,setPrototypeOf:je}=Ee,{toString:Te}=Ee.prototype,{slice:xe}=be.prototype,{get:Re}=$e(Node.prototype,"nodeType"),ke=we?{}:{Attr:ye(Attr),CanvasRenderingContext2D:ye(CanvasRenderingContext2D),CSSStyleDeclaration:ye(CSSStyleDeclaration),Document:ye(Document),Element:ye(Element),HTMLCanvasElement:ye(HTMLCanvasElement),HTMLElement:ye(HTMLElement),HTMLImageElement:ye(HTMLImageElement),HTMLScriptElement:ye(HTMLScriptElement),MutationRecord:ye(MutationRecord),Node:ye(Node),ShadowRoot:ye(ShadowRoot),get CSS2Properties(){return ke.CSSStyleDeclaration}},Pe=(e,t)=>{if("Element"!==t&&t in ke)return ke[t](e);if(Se(e))return je(e,me.prototype);const r=(e=>i(xe,i(Te,e),8,-1))(e);if(r in ke)return ke[r](e);if(r in Q)return je(e,Q[r].prototype);if("nodeType"in e)switch(i(Re,e)){case 1:if(!(t in ke))throw new Error("unknown hint "+t);return ke[t](e);case 2:return ke.Attr(e);case 3:return ke.Node(e);case 9:return ke.Document(e)}throw new Error("unknown brand "+r)};var Ae=we?e=>e===window||e===globalThis?Q:e:ie(((e,t="Element")=>{if(e===window||e===globalThis)return Q;switch(typeof e){case"object":return e&&Pe(e,t);case"string":return new be(e);case"number":return new ve(e);default:throw new Error("unsupported value")}}));const Oe={get(e,t){const r=e;for(;!m(e,t);)e=w(e);const{get:n,set:s}=g(e,t);return function(){return arguments.length?o(s,r,arguments):i(n,r)}}},Le=t=>new e(t,Oe);let{Math:Me,setInterval:Ne,performance:Ie}=Ae(window);const Ce={mark(){},end(){},toString:()=>"{mark(){},end(){}}"};let We=!0;function Fe(e,t=10){if(We)return Ce;function r(){let e=Ae([]);for(let{name:t,duration:r}of Ie.getEntriesByType("measure"))e.push({name:t,duration:r});e.length&&Ie.clearMeasures()}return Fe[e]||(Fe[e]=Ne(r,Me.round(6e4/Me.min(60,t)))),{mark(){Ie.mark(e)},end(t=!1){Ie.measure(e,e);const n=Ie.getEntriesByName(e,"measure"),o=n.length>0?n[n.length-1]:null;console.log("PROFILER:",o),Ie.clearMarks(e),t&&(clearInterval(Fe[e]),delete Fe[e],r())}}}let{Array:De,document:He,Math:qe,RegExp:Je}=Ae(window);function Be(e){let{length:t}=e;if(t>1&&"/"===e[0]){let r="/"===e[t-1];if(r||t>2&&Ae(e).endsWith("/i")){let t=[Ae(e).slice(1,r?-1:-2)];return r||t.push("i"),new Je(...t)}}return new Je(Ae(e).replace(/[-/\\^$*+?.()|[\]{}]/g,"\\$&"))}function ze(e){const t=S();if("function"==typeof t.sendSnippetHitEvent)try{t.sendSnippetHitEvent(e,He.location.hostname)}catch(e){}}function _e(){return Ae(qe.floor(2116316160*qe.random()+60466176)).toString(36)}function Xe(e){return Ae(De.from(e)).map((e=>`'${e}'`)).join(" ")}let Ue=!1,Ve=null;function Ge(){return Ue}const{console:Ke}=Ae(window),Qe=()=>{};function Ye(...e){let{mark:t,end:r}=Fe("log");if(Ge()){const t=["%c DEBUG","font-weight: bold;"],r=e.indexOf("error"),n=e.indexOf("warn"),o=e.indexOf("success"),s=e.indexOf("info");-1!==r?(t[0]+=" - ERROR",t[1]+="color: red; border:2px solid red",Ae(e).splice(r,1)):-1!==n?(t[0]+=" - WARNING",t[1]+="color: orange; border:2px solid orange ",Ae(e).splice(n,1)):-1!==o?(t[0]+=" - SUCCESS",t[1]+="color: green; border:2px solid green",Ae(e).splice(o,1)):-1!==s&&(t[1]+="color: black;",Ae(e).splice(s,1)),Ae(e).unshift(...t);const i=Ve;if(i){if(!Ae(e).some((e=>Ae(i).test(e))))return}}t(),Ke.log(...e),r()}function Ze(e){return s(Ge()?Ye:Qe,null,e)}const{Function:et,Object:tt,WeakMap:rt}=Ae(window);let nt=!1;const ot=new rt;function st(e,t){nt||function(){const{toString:e}=et.prototype,t=l(e,(function(){const t=ot.get(this);return o(e,void 0!==t?t:this,arguments)}));tt.defineProperty(window.Function.prototype,"toString",{value:t}),ot.set(t,e),nt=!0}(),ot.set(e,t)}let{parseFloat:it,variables:at,clearTimeout:ct,fetch:lt,setTimeout:pt,Array:ut,Error:ft,Map:dt,Object:ht,ReferenceError:gt,Set:yt,WeakMap:wt}=Ae(window),{onerror:mt}=Le(window),vt=Node.prototype,bt=Element.prototype,Et=null;function St(e,t,r,n=!0){let o=Ae(t),s=o.indexOf(".");if(-1==s){let o=ht.getOwnPropertyDescriptor(e,t);if(o&&!o.configurable)return;let s=ht.assign({},r,{configurable:n});if(!o&&!s.get&&s.set){let r=e[t];s.get=()=>r}return void ht.defineProperty(e,t,s)}let i=o.slice(0,s).toString();t=o.slice(s+1).toString();let a=e[i];!a||"object"!=typeof a&&"function"!=typeof a||St(a,t,r);let c=ht.getOwnPropertyDescriptor(e,i);if(c&&!c.configurable)return;Et||(Et=new wt),Et.has(e)||Et.set(e,new dt);let l=Et.get(e);if(l.has(i))return void l.get(i).set(t,r);let p=new dt([[t,r]]);l.set(i,p),ht.defineProperty(e,i,{get:()=>a,set(e){if(a=e,a&&("object"==typeof a||"function"==typeof a))for(let[e,t]of p)St(a,e,t)},configurable:n})}function $t(e){let t=mt();mt(((...r)=>{let n=r.length&&r[0];return!("string"!=typeof n||!Ae(n).includes(e))||("function"==typeof t?o(t,this,r):void 0)}))}function jt(e,t,r,n="",o=!0){let s=Ze(e);if(!r)return void s("error","no property to abort on read");let i=_e(),a=!1;s("info",`aborting on ${r} access`),St(t,r,{get:function(){throw s("success",`${r} access aborted`,`\nFILTER: ${e} ${n}`),a||(a=!0,ze(`${e} ${n}`)),new gt(i)},set(){}},o),$t(i)}function Tt(e,t,r,n="",o=!0){let s=Ze(e);if(!r)return void s("error","no property to abort on write");let i=_e(),a=!1;s("info",`aborting when setting ${r}`),St(t,r,{set:function(){throw s("success",`setting ${r} aborted`,`\nFILTER: ${e} ${n}`),a||(a=!0,ze(`${e} ${n}`)),new gt(i)}},o),$t(i)}function xt(e,t=!1,r=!1){let n=at.abortedIframes,s=at.iframePropertiesToAbort;const a=Xe(e);for(let o of ut.from(window.frames))if(n.has(o))for(let s of e)t&&n.get(o).read.add({property:s,formattedProperties:a}),r&&n.get(o).write.add({property:s,formattedProperties:a});for(let n of e)t&&s.read.add({property:n,formattedProperties:a}),r&&s.write.add({property:n,formattedProperties:a});function c(){for(let e of ut.from(window.frames)){n.has(e)||n.set(e,{read:new yt(s.read),write:new yt(s.write)});let t=n.get(e).read;if(t.size>0){let r=ut.from(t);t.clear();for(let{property:t,formattedProperties:n}of r)jt("abort-on-iframe-property-read",e,t,n)}let r=n.get(e).write;if(r.size>0){let t=ut.from(r);r.clear();for(let{property:r,formattedProperties:n}of t)Tt("abort-on-iframe-property-write",e,r,n)}}}c(),n.has(document)||(n.set(document,!0),function(e){let t;function r(e,t){for(let r of t){St(e,r,n(e,r))}}function n(t,r){let n=t[r],s=function(...t){let r;return r=o(n,this,t),e&&e(),r};return st(s,n),{get:()=>s}}function s(t,r){let n=ht.getOwnPropertyDescriptor(t,r),{set:o}=n||{};return{set(t){let r;return r=i(o,this,t),e&&e(),r}}}r(vt,["appendChild","insertBefore","replaceChild"]),r(bt,["append","prepend","replaceWith","after","before","insertAdjacentElement","insertAdjacentHTML"]),t=s(bt,"innerHTML"),St(bt,"innerHTML",t),t=s(bt,"outerHTML"),St(bt,"outerHTML",t)}(c))}let{Object:Rt}=window;function kt(e,t){if(!(e instanceof Rt))return;let r=e,n=Ae(t).split(".");if(0===n.length)return;for(let e=0;e<n.length-1;e++){let t=n[e];if(!m(r,t))return;if(r=r[t],!(r instanceof Rt))return}let o=n[n.length-1];return m(r,o)?[r,o]:void 0}const Pt=Ae(/^\d+$/);function At(e){switch(e){case"false":return!1;case"true":return!0;case"falseStr":return"false";case"trueStr":return"true";case"null":return null;case"noopFunc":return()=>{};case"trueFunc":return()=>!0;case"falseFunc":return()=>!1;case"emptyArray":return[];case"emptyObj":return{};case"undefined":return;case"":return e;default:return Pt.test(e)?it(e):e}}function Ot(e,t){if(!e||!e.length)return!0;const r=_e(),n=new ft(r),o=new URL(self.location.href);o.hash="";const s=/(.*?@)?(\S+)(:\d+):\d+\)?$/,i=[];for(let e of n.stack.split(/[\n\r]+/)){if(Ae(e).includes(r))continue;e=Ae(e).trim();const t=Ae(s).exec(e);if(null===t)continue;let n=t[2];Ae(n).startsWith("(")&&(n=Ae(n).slice(1)),n===o.href?n="inlineScript":Ae(n).startsWith("<anonymous>")&&(n="injectedScript");let a=t[1]?Ae(t[1]).slice(0,-1):Ae(e).slice(0,Ae(t).index).trim();Ae(a).startsWith("at")&&(a=Ae(a).slice(2).trim());let c=t[3];Ae(i).push(" "+`${a} ${n}${c}:1`.trim())}i[0]="stackDepth:"+(i.length-1);const a=Ae(i).join("\n");for(let r of e){if(Be(r).test(a))return t("info",`Found needle in stack trace: ${r}`),!0}return t("info",`Stack trace does not match any needle. Stack trace: ${a}`),!1}new dt;let{HTMLScriptElement:Lt,Object:Mt,ReferenceError:Nt}=Ae(window),It=Mt.getPrototypeOf(Lt);const{Error:Ct,Object:Wt,Array:Ft,Map:Dt}=Ae(window);let Ht=null;const qt=new Set;function Jt(e){qt.has(e)||(qt.add(e),ze(e))}function Bt(e,t,r){let n=e;for(const e of r){if(!n||!m(n,e))return!1;n=n[e]}if("string"==typeof n||"number"==typeof n){const e=n.toString();return t.test(e)}return!1}const{Array:zt,Blob:_t,Error:Xt,Object:Ut,Reflect:Vt}=Ae(window),Gt=[],Kt=new Set;let{Error:Qt,URL:Yt}=Ae(window),{cookie:Zt}=Le(document);const{Map:er,Object:tr,Reflect:rr,WeakMap:nr}=Ae(window),or=window.EventTarget.prototype.addEventListener,sr=window.EventTarget.prototype.removeEventListener,ir=new nr;let ar=[];const cr=new Set;function lr(e){cr.has(e)||(cr.add(e),ze(e))}let{console:pr,document:ur,getComputedStyle:fr,isExtensionContext:dr,variables:hr,Array:gr,MutationObserver:yr,Object:wr,DOMMatrix:mr,XPathEvaluator:vr,XPathExpression:br,XPathResult:Er}=Ae(window);const{querySelectorAll:Sr}=ur,$r=Sr&&s(Sr,ur);function jr(e,t=!1){return Rr(e,$r.bind(ur),ur,t)}function Tr(e,t,r,n){const o=t.getAttribute("xlink:href")||t.getAttribute("href");if(o){const i=$r(o)[0];if(!i&&Ge())return pr.log("No elements found matching",o),!1;if(!(s=e)||0===s.length||s.every((e=>""===e.trim()))){const e=n.length>0?n:[];return r.push({element:i,rootParents:[...e,t]}),!1}const a=i.querySelectorAll.bind(i);return{nextBoundElement:i,nestedSelectorsString:e.join("^^"),next$$:a}}var s}function xr(e,t){const r=function(e,t=!1){try{const r=navigator.userAgent.includes("Firefox")?e.openOrClosedShadowRoot:browser.dom.openOrClosedShadowRoot(e);return null===r&&Ge()&&!t&&pr.log("Shadow root not found or not added in element yet",e),r}catch(r){return Ge()&&!t&&pr.log("Error while accessing shadow root",e,r),null}}(t);if(r){const{querySelectorAll:n}=r,o=n&&s(n,r).bind(r);return{nextBoundElement:t,nestedSelectorsString:":host "+e.join("^^"),next$$:o}}return!1}function Rr(e,t,r,n,o=[]){if(e.includes("^^")){const[s,i,...a]=e.split("^^");let c,l;switch(i){case"svg":l=Tr;break;case"sh":l=xr;break;default:return Ge()&&pr.log(i," is not supported. Supported commands are: \n^^sh^^\n^^svg^^"),[]}c=""===s.trim()?[r]:t(s);const p=[];for(const e of c){const t=l(a,e,p,o);if(!t)continue;const{next$$:r,nestedSelectorsString:s,nextBoundElement:i}=t,c=Rr(s,r,i,n,[...o,e]);c&&p.push(...c)}return p}const s=t(e);return n?[...s].map((e=>({element:e,rootParents:o.length>0?o:[]}))):s}const{assign:kr,setPrototypeOf:Pr}=wr;class Ar extends br{evaluate(...e){return Pr(o(super.evaluate,this,e),Er.prototype)}}class Or extends vr{createExpression(...e){return Pr(o(super.createExpression,this,e),Ar.prototype)}}function Lr(e){if(hr.hidden.has(e))return!1;!function(e){dr&&"function"==typeof checkElement&&checkElement(e)}(e),hr.hidden.add(e);let{style:t}=Ae(e),r=Ae(t,"CSSStyleDeclaration"),n=Ae([]);const o=S();let{debugCSSProperties:s}=o;for(let[e,t]of s||[["display","none"]])r.setProperty(e,t,"important"),n.push([e,r.getPropertyValue(e)]);return new yr((()=>{for(let[e,t]of n){let n=r.getPropertyValue(e),o=r.getPropertyPriority(e);n==t&&"important"==o||r.setProperty(e,t,"important")}})).observe(e,{attributes:!0,attributeFilter:["style"]}),!0}function Mr(e){let t=e;if(t.startsWith("xpath(")&&t.endsWith(")")){let t=function(e){let t=e;if(t.startsWith("xpath(")&&t.endsWith(")")){let e=t.slice(6,-1),r=(new Or).createExpression(e,null),n=Er.ORDERED_NODE_SNAPSHOT_TYPE;return e=>{if(!e)return;let t=r.evaluate(ur,n,null),{snapshotLength:o}=t;for(let r=0;r<o;r++)e(t.snapshotItem(r))}}return t=>jr(e).forEach(t)}(e);return()=>{let e=Ae([]);return t((t=>e.push(t))),e}}return()=>gr.from(jr(e))}let{ELEMENT_NODE:Nr,TEXT_NODE:Ir,prototype:Cr}=Node,{prototype:Wr}=Element,{prototype:Fr}=HTMLElement,{console:Dr,variables:Hr,DOMParser:qr,Error:Jr,MutationObserver:Br,Object:zr,ReferenceError:_r}=Ae(window),{getOwnPropertyDescriptor:Xr}=zr;const{CanvasRenderingContext2D:Ur,document:Vr,Map:Gr,MutationObserver:Kr,Object:Qr,Set:Yr,WeakMap:Zr,WeakSet:en}=Ae(window);let tn,rn=new Zr,nn=new en,on=new Yr,sn=new en;const an=new Yr;function cn(e,t,r,n){nn.add(e),rn.delete(e);const o=Ae(e).closest(t.selector);if(o&&!sn.has(o)){Lr(o),sn.add(o),Ze("hide-if-canvas-contains")("success","Matched: ",o,`\nFILTER: hide-if-canvas-contains ${t.formattedArguments}`);const e="hide-if-canvas-contains "+t.formattedArguments;an.has(e)||(an.add(e),ze(e))}else!function(e,t,r,n){on.add({canvasElement:e,rule:t,functionName:r,text:n})}(e,t,r,n)}Ae(window);const{Map:ln,MutationObserver:pn,Object:un,Set:fn,WeakSet:dn}=Ae(window);let hn=Element.prototype,{attachShadow:gn}=hn,yn=new dn,wn=new ln;const mn=new fn;let vn=null;const{Error:bn,Object:En,Array:Sn,parseFloat:$n,isNaN:jn}=Ae(window);class Tn{constructor(e){if("string"!=typeof e)throw new bn("JSONPath: query must be a string");if(!e.length)throw new bn("JSONPath: query must be a non-empty string");this._steps=this._tokenize(e)}_tokenize(e){e=Ae(e);const t=new Sn;let r=0;for("$"===e[0].toString()&&(r=1);r<e.length;){let n=!1;if(e.startsWith("..",r)?(n=!0,r+=2):"."===e[r].toString()&&r++,"["===e[r].toString()){const o=e.indexOf("]",r);if(-1===o)throw new bn(`JSONPath: unclosed bracket in query "${e}"`);const s=e.slice(r+1,o);if(!s.length)throw new bn(`JSONPath: empty bracket notation in query "${e}"`);s.startsWith("?(")?t.push({type:"filter",key:"?",filter:this._parseFilter(s),recursive:n}):t.push({type:"direct",key:s.replace(/['"]/g,"").toString(),recursive:n}),r=o+1}else{const o=e.slice(r).search(/[.[]/),s=-1===o?e.slice(r).toString():e.slice(r,r+o).toString();if(!s&&!n)throw new bn(`JSONPath: trailing dot with no property name in query "${e}"`);(s||n)&&t.push({type:"direct",key:s||"*",recursive:n}),r+=s.length}}return t}_parseFilter(e){const t=(e=Ae(e)).match(/(?:[@.]?)([\w]+(?:\.[\w]+)*)\s*([!=^$*]=|[<>]=?)\s*(?:['"](.+?)['"]|([\w.+-]+))\)/);if(!t)throw new bn(`JSONPath: invalid filter expression "${e}"`);return{property:t[1],operator:t[2],target:null!=t[3]?t[3]:t[4]}}evaluate(e){if(!e||"object"!=typeof e)throw new bn("JSONPath: evaluate() requires an object or array");let t=Ae([{parent:{root:e},key:"root"}]);for(const e of this._steps){const r=[];for(const{parent:n,key:o}of t){const t=n[o];t&&"object"==typeof t&&(e.recursive?this._deepSearch(t,e,r):this._match(t,e,r))}t=r}return t}_match(e,t,r){const n="*"===t.key||"?"===t.key?En.keys(e):[t.key];for(const o of n)if(m(e,o)){if("?"===t.key&&!this._test(e[o],t.filter))continue;r.push({parent:e,key:o})}}_deepSearch(e,t,r,n=1e4){if(this._match(e,t,r),!(n<=0))for(const o of En.keys(e))e[o]&&"object"==typeof e[o]&&this._deepSearch(e[o],t,r,n-1)}_test(e,t){if(!t||!e)return!1;let r=e;for(const e of Ae(t.property).split(".")){if(null==r||"object"!=typeof r)return!1;r=r[e]}const n=Ae(r),o=Ae(t.target),s=n.toString(),i=o.toString(),a=$n(n),c=$n(o),l=!jn(a)&&!jn(c);switch(t.operator){case"==":return l?a===c:s===i;case"!=":return l?a!==c:s!==i;case"<":return l?a<c:s<i;case"<=":return l?a<=c:s<=i;case">":return l?a>c:s>i;case">=":return l?a>=c:s>=i;case"^=":return n.startsWith(o);case"$=":return n.endsWith(o);case"*=":return n.includes(o);default:return!1}}}const{Array:xn,Error:Rn,JSON:kn,Map:Pn,Object:An,Response:On}=Ae(window);let Ln=null;const Mn=new Set;function Nn(e){Mn.has(e)||(Mn.add(e),ze(e))}let{Array:In,Error:Cn,JSON:Wn,Map:Fn,Object:Dn,Response:Hn}=Ae(window),qn=null;const Jn=new Set;function Bn(e){Jn.has(e)||(Jn.add(e),ze(e))}const{Error:zn,Object:_n,Map:Xn}=Ae(window);let Un=null;const Vn=new Set;function Gn(e){Vn.has(e)||(Vn.add(e),ze(e))}function Kn(e,t,r){if(!r.length){if("string"==typeof e||"number"==typeof e){const r=e.toString();return t.test(r)}return!1}let n=e;for(const e of r){if(!n||!m(n,e))return!1;n=n[e]}if("string"==typeof n||"number"==typeof n){const e=n.toString();return t.test(e)}return!1}let{Error:Qn}=Ae(window);const{Array:Yn,addEventListener:Zn,Error:eo,Object:to,Reflect:ro,Set:no,WeakSet:oo}=Ae(window),so=new oo,io=new Yn,ao=new no,co=new no;let{Error:lo,Map:po,Object:uo,console:fo}=Ae(window),{toString:ho}=Function.prototype,go=EventTarget.prototype,{addEventListener:yo}=go,wo=null;const mo=new Set;let{fetch:vo}=Ae(window),bo=!1;const Eo=[],So=[],$o=()=>{if(!bo){let e=l(vo,((...e)=>{let[t]=e;if(Eo.length>0&&"string"==typeof t){let r;try{r=new URL(t)}catch(e){if(!(e instanceof TypeError))throw e;r=new URL(t,Ae(document).location)}Eo.forEach((e=>e(r))),e[0]=r.href}return o(vo,self,e).then((e=>{let t=e;return So.forEach((e=>{t=e(t)})),t}))}));st(e,window.fetch),window.fetch=e,bo=!0}};let jo,{Map:To,Object:xo,RegExp:Ro,Response:ko}=Ae(window);const Po=new Set;const{Error:Ao,Object:Oo,atob:Lo,btoa:Mo,RegExp:No}=Ae(window);let{XMLHttpRequest:Io,WeakMap:Co,Object:Wo}=Ae(window),Fo=!1;const Do=[],Ho=[],qo=new Co,Jo=()=>{if(Fo)return;const e=class extends Io{open(e,t,...r){return qo.set(this,{method:e,url:t}),super.open(e,t,...r)}send(e){let t=e;if("string"==typeof e&&Do.length>0)for(const e of Do)t=e(t);return super.send(t)}get response(){const e=super.response;if(0===Ho.length)return e;const t=qo.get(this);if(void 0===t)return e;const r="string"==typeof e?e.length:void 0;if(t.lastResponseLength!==r&&(t.cachedResponse=void 0,t.lastResponseLength=r),void 0!==t.cachedResponse)return t.cachedResponse;if("string"!=typeof e)return t.cachedResponse=e;let n=e;for(const e of Ho)n=e(n);return t.cachedResponse=n}get responseText(){const e=this.response;return"string"!=typeof e?super.responseText:e}};st(e,window.XMLHttpRequest),st(e.prototype.open,window.XMLHttpRequest.prototype.open),st(e.prototype.send,window.XMLHttpRequest.prototype.send),st(Wo.getOwnPropertyDescriptor(e.prototype,"response").get,Wo.getOwnPropertyDescriptor(window.XMLHttpRequest.prototype,"response").get),st(Wo.getOwnPropertyDescriptor(e.prototype,"responseText").get,Wo.getOwnPropertyDescriptor(window.XMLHttpRequest.prototype,"responseText").get),window.XMLHttpRequest=e,Fo=!0};let Bo,{Array:zo,Error:_o,JSON:Xo,Object:Uo,RegExp:Vo}=Ae(window);const Go=new Set;let Ko,{JSON:Qo,RegExp:Yo}=Ae(window);const Zo=new Set;let es,{delete:ts,has:rs}=c(URLSearchParams.prototype);const ns=new Set;const{Error:os,Object:ss,parseInt:is,isNaN:as}=Ae(window),{toString:cs}=Function.prototype,ls=window.setTimeout,ps=window.setInterval,us={TIMEOUT:"timeout",INTERVAL:"interval",BOTH:"both"};let fs=null;const ds=new Set;const hs={"abort-current-inline-script":function(e,t=null){const r=Xe(arguments),n=Ze("abort-current-inline-script"),{mark:o,end:s}=Fe("abort-current-inline-script"),a=t?Be(t):null,c=_e(),l=Ae(document).currentScript;let p=!1,u=window;const f=Ae(e).split("."),d=Ae(f).pop();for(let e of Ae(f))if(u=u[e],!u||"object"!=typeof u&&"function"!=typeof u)return void n("warn",f," is not found");const{get:h,set:g}=Mt.getOwnPropertyDescriptor(u,d)||{};let y=u[d];void 0===y&&n("warn","The property",d,"doesn't exist yet. Check typos.");const w=()=>{const e=Ae(document).currentScript;if(e instanceof It&&""==Ae(e,"HTMLScriptElement").src&&e!=l&&(!a||a.test(Ae(e).textContent)))throw n("success",f," is aborted \n",e,"\nFILTER: abort-current-inline-script",r),p||(p=!0,ze("abort-current-inline-script "+r)),new Nt(c)},m={get(){return w(),h?i(h,this):y},set(e){w(),g?i(g,this,e):y=e}};o(),St(u,d,m),s(),$t(c)},"abort-on-iframe-property-read":function(...e){const{mark:t,end:r}=Fe("abort-on-iframe-property-read");t(),xt(e,!0,!1),r()},"abort-on-iframe-property-write":function(...e){const{mark:t,end:r}=Fe("abort-on-iframe-property-write");t(),xt(e,!1,!0),r()},"abort-on-property-read":function(e,t){const r=!("false"===t),n=Xe(arguments),{mark:o,end:s}=Fe("abort-on-property-read");o(),jt("abort-on-property-read",window,e,n,r),s()},"abort-on-property-write":function(e,t){const r=Xe(arguments),{mark:n,end:o}=Fe("abort-on-property-write"),s=!("false"===t);n(),Tt("abort-on-property-write",window,e,r,s),o()},"array-override":function(e,t,r="false",n,s){if(!e)throw new Ct("[array-override snippet]: Missing method to override.");if(!t)throw new Ct("[array-override snippet]: Missing needle.");Ht||(Ht=new Dt);let i=Ze("array-override");const{mark:a,end:c}=Fe("array-override"),p=Xe(arguments);if("push"!==e||Ht.has("push"))if("includes"!==e||Ht.has("includes")){if("forEach"===e&&!Ht.has("forEach")){a();const{forEach:e}=Ft.prototype;Ht.set("forEach",Ae([]));let t=l(e,(function(t,r){const n=Ht.get("forEach");return o(e,this,[function(e,s,a){for(const{needleRegex:t,pathSegments:r,stackNeedles:o,formattedArgs:s}of n)if(r.length||"string"!=typeof e&&"number"!=typeof e){if(r.length&&"object"==typeof e&&null!==e&&Bt(e,t,r)&&Ot(o,i))return i("success",`Array.forEach skipped callback for object containing needle: ${t}\nFILTER: array-override ${s}`),void Jt("array-override "+s)}else{const r=e.toString();if(r.match&&r.match(t)&&Ot(o,i))return i("success",`Array.forEach skipped callback for item matching needle: ${t}\nFILTER: array-override ${s}`),void Jt("array-override "+s)}return o(t,r||this,[e,s,a])},r])}));st(t,e),Wt.defineProperty(window.Array.prototype,"forEach",{value:t}),i("info","Wrapped Array.prototype.forEach"),c()}}else{a();const{includes:e}=Ft.prototype;Ht.set("includes",Ae([]));let t=l(e,(function(t){const r=Ht.get("includes");for(const{needleRegex:e,retVal:n,pathSegments:o,stackNeedles:s,formattedArgs:a}of r)if(o.length||"string"!=typeof t&&"number"!=typeof t){if(o.length&&"object"==typeof t&&null!==t&&Bt(t,e,o)&&Ot(s,i))return i("success",`Array.includes returned ${n} for object containing ${e}\nFILTER: array-override ${a}`),Jt("array-override "+a),n}else if(t.toString().match&&t.toString().match(e)&&Ot(s,i))return i("success",`Array.includes returned ${n} for ${e}\nFILTER: array-override ${a}`),Jt("array-override "+a),n;return o(e,this,arguments)}));st(t,e),Wt.defineProperty(window.Array.prototype,"includes",{value:t}),i("info","Wrapped Array.prototype.includes"),c()}else{a();const{push:e}=Ft.prototype;Ht.set("push",Ae([]));let t=l(e,(function(t){const r=Ht.get("push");for(const{needleRegex:e,pathSegments:n,stackNeedles:o,formattedArgs:s}of r)if(n.length||"string"!=typeof t&&"number"!=typeof t){if(n.length&&"object"==typeof t&&null!==t&&Bt(t,e,n)&&Ot(o,i))return i("success",`Array.push is ignored for object containing needle: ${e}\nFILTER: array-override ${s}`),void Jt("array-override "+s)}else{const r=t.toString();if(r.match&&r.match(e)&&Ot(o,i))return i("success",`Array.push is ignored for needle: ${e}\nFILTER: array-override ${s}`),void Jt("array-override "+s)}return o(e,this,arguments)}));st(t,e),Wt.defineProperty(window.Array.prototype,"push",{value:t}),i("info","Wrapped Array.prototype.push"),c()}const u=Be(t);let f=[];n&&(f=n.split("."));let d=[];s&&(d=s.split(",").map((e=>e.trim())));const h=Ht.get(e),g="true"===r;h.push({needleRegex:u,retVal:g,pathSegments:f,stackNeedles:d,formattedArgs:p}),Ht.set(e,h)},"blob-override":function(e,t="",r=null){if(!e)throw new Xt("[blob-override snippet]: Missing parameter search.");const n=Ze("blob-override"),o=Xe(arguments),{mark:s,end:i}=Fe("blob-override");if(s(),Gt.push({match:Be(e),replaceWith:t,needle:r?Be(r):null,formattedArgs:o}),Gt.length>1)return;const a=_t;function c(e,t={}){if(zt.isArray(e)){let t=Ae(e).join("");for(const e of Ae(Gt))if((!e.needle||e.needle.test(t))&&e.match.test(t)){t=t.replace(e.match,e.replaceWith),n("success",`Replaced: ${e.match} → ${e.replaceWith},\nFILTER: blob-override ${e.formattedArgs}`);const r="blob-override "+e.formattedArgs;Kt.has(r)||(Kt.add(r),ze(r))}e=[t]}const r=Vt.construct(a,[e,t]);return Ut.setPrototypeOf(r,c.prototype),r}c.prototype=a.prototype,Ut.setPrototypeOf(c,a),st(c,window.Blob),window.Blob=c,n("info","Wrapped Blob constructor in context "),i()},"cookie-remover":function(e,t=!1){if(!e)throw new Qt("[cookie-remover snippet]: No cookie to remove.");const r=Xe(arguments);let n=Ze("cookie-remover");const{mark:o,end:s}=Fe("cookie-remover");let i=Be(e),a=!1;if(!Ae(/^http|^about/).test(location.protocol))return void n("warn","Snippet only works for http or https and about.");function c(){return Ae(Zt()).split(";").filter((e=>i.test(Ae(e).split("=")[0])))}const l=()=>{n("info","Parsing cookies for matches"),o();for(const e of Ae(c())){let t=Ae(location.hostname);!t&&Ae(location.ancestorOrigins)&&Ae(location.ancestorOrigins[0])&&(t=new Yt(Ae(location.ancestorOrigins[0])).hostname);const o=Ae(e).split("=")[0],s="expires=Thu, 01 Jan 1970 00:00:00 GMT",i="path=/",c=t.split(".");for(let e=c.length;e>0;e--){const t=c.slice(c.length-e).join(".");Zt(`${Ae(o).trim()}=;${s};${i};domain=${t}`),Zt(`${Ae(o).trim()}=;${s};${i};domain=.${t}`),n("success",`Set expiration date on ${o}`,"\nFILTER: cookie-remover",r),a||(a=!0,ze("cookie-remover "+r))}}s()};if(l(),t){let e=c();setInterval((()=>{let t=c();if(t!==e)try{l()}finally{e=t}}),1e3)}},debug:function(e){Ue=!0,e&&(Ve=Be(e))},"event-override":function(e,t,r=null){const n=Xe(arguments),s={eventType:e,mode:t,needle:r?Be(r):null,formattedArgs:n};if(ar.includes(s)||ar.push(s),ar.length>1)return;let a=Ze("[event-override]");const{mark:c,end:p}=Fe("event-override"),u=tr.getOwnPropertyDescriptor(window.EventTarget.prototype,"addEventListener");if(u.configurable){let e=l(or,(function(e,t,r){c();const n=ar.filter((t=>t.eventType===e));if(!n.length||e!==n[0].eventType)return p(),o(or,this,arguments);const s=n.find((e=>"disable"===e.mode&&(!e.needle||e.needle.test(t.toString()))));if(s)return a("success",`Disabling ${s.eventType} event, \nFILTER: event-override ${s.formattedArgs}`),lr("event-override "+s.formattedArgs),void p();const l=n.filter((e=>"trusted"===e.mode&&(!e.needle||e.needle.test(t.toString()))));if("function"!=typeof t&&(!t||"function"!=typeof t.handleEvent)||!l.length||e!==l[0].eventType)return p(),o(or,this,arguments);const u=function(e){const r=new Proxy(e,{get(t,r){if("isTrusted"===r)return a("success",`Providing trusted value for ${e.type} event`),lr("event-override "+l[0].formattedArgs),!0;const n=rr.get(t,r);return"function"==typeof n?function(...e){return o(n,t,e)}:n}});return"function"==typeof t?i(t,this,r):i(t.handleEvent,t,r)};return u.originalListener=t,ir.has(t)||ir.set(t,new er),ir.get(t).set(e,u),a("info",`\nWrapping event listener for ${e}`),p(),o(or,this,[e,u,r])}));st(e,or),tr.defineProperty(window.EventTarget.prototype,"addEventListener",{...u,value:e})}const f=tr.getOwnPropertyDescriptor(window.EventTarget.prototype,"removeEventListener");if(f.configurable){let e=l(sr,(function(e,t,r){if(t&&ir.has(t)&&ir.get(t).has(e)){const n=ir.get(t).get(e);return ir.get(t).delete(e),o(sr,this,[e,n,r])}return o(sr,this,arguments)}));st(e,sr),tr.defineProperty(window.EventTarget.prototype,"removeEventListener",{...f,value:e})}a("info","Initialized event-override snippet")},"freeze-element":function(e,t="",...r){const n=Xe(arguments);let s,a,c=!1,l=!1,p=Ae(r).filter((e=>!g(e))),u=Ae(r).filter((e=>g(e))).map(Be),f=_e(),d=Mr(e);!function(){let r=Ae(t).split("+");1===r.length&&""===r[0]&&(r=[]);for(let t of r)switch(t){case"subtree":c=!0;break;case"abort":l=!0;break;default:throw new Jr("[freeze] Unknown option passed to the snippet. [selector]: "+e+" [option]: "+t)}}();let h={selector:e,shouldAbort:l,rid:f,exceptionSelectors:p,regexExceptions:u,changeId:0};function g(e){return e.length>=2&&"/"==e[0]&&"/"==e[e.length-1]}function y(){a=d(),w(a,!1)}function w(e,t=!0){for(let r of e)Hr.frozen.has(r)||(Hr.frozen.set(r,h),!t&&c&&new Br((e=>{for(let t of Ae(e))w(Ae(t,"MutationRecord").addedNodes)})).observe(r,{childList:!0,subtree:!0}),c&&Ae(r).nodeType===Nr&&w(Ae(r).childNodes))}function m(e,...t){Ye(`[freeze][${e}] `,...t)}function v(e,t,r,n){let o=n.selector,s=n.changeId,i="string"==typeof e,a=n.shouldAbort?"aborting":"watching";switch(Dr.groupCollapsed(`[freeze][${s}] ${a}: ${o}`),r){case"appendChild":case"append":case"prepend":case"insertBefore":case"replaceChild":case"insertAdjacentElement":case"insertAdjacentHTML":case"insertAdjacentText":case"innerHTML":case"outerHTML":m(s,i?"text: ":"node: ",e),m(s,"added to node: ",t);break;case"replaceWith":case"after":case"before":m(s,i?"text: ":"node: ",e),m(s,"added to node: ",Ae(t).parentNode);break;case"textContent":case"innerText":case"nodeValue":m(s,"content of node: ",t),m(s,"changed to: ",e)}m(s,`using the function "${r}"`),Dr.groupEnd(),n.changeId++}function b(e,t){if(t)for(let r of t)if(r.test(e))return!0;return!1}Hr.frozen.has(document)||(Hr.frozen.set(document,!0),function(){let e;function t(e){return e&&Hr.frozen.has(e)}function r(e){try{return e&&(Hr.frozen.has(e)||Hr.frozen.has(Ae(e).parentNode))}catch(e){return!1}}function n(e,t){try{return e&&(Hr.frozen.has(e)&&t||Hr.frozen.has(Ae(e).parentNode)&&!t)}catch(e){return!1}}function o(e){return Hr.frozen.get(e)}function s(e){try{if(Hr.frozen.has(e))return Hr.frozen.get(e);let t=Ae(e).parentNode;return Hr.frozen.get(t)}catch(e){}}function i(e,t){try{if(Hr.frozen.has(e)&&t)return Hr.frozen.get(e);let r=Ae(e).parentNode;return Hr.frozen.get(r)}catch(e){}}e=x(Cr,"appendChild",t,o),St(Cr,"appendChild",e),e=x(Cr,"insertBefore",t,o),St(Cr,"insertBefore",e),e=x(Cr,"replaceChild",t,o),St(Cr,"replaceChild",e),e=R(Wr,"append",t,o),St(Wr,"append",e),e=R(Wr,"prepend",t,o),St(Wr,"prepend",e),e=R(Wr,"replaceWith",r,s),St(Wr,"replaceWith",e),e=R(Wr,"after",r,s),St(Wr,"after",e),e=R(Wr,"before",r,s),St(Wr,"before",e),e=k(Wr,"insertAdjacentElement",n,i),St(Wr,"insertAdjacentElement",e),e=k(Wr,"insertAdjacentHTML",n,i),St(Wr,"insertAdjacentHTML",e),e=k(Wr,"insertAdjacentText",n,i),St(Wr,"insertAdjacentText",e),e=P(Wr,"innerHTML",t,o),St(Wr,"innerHTML",e),e=P(Wr,"outerHTML",r,s),St(Wr,"outerHTML",e),e=A(Cr,"textContent",t,o),St(Cr,"textContent",e),e=A(Fr,"innerText",t,o),St(Fr,"innerText",e),e=A(Cr,"nodeValue",t,o),St(Cr,"nodeValue",e)}()),s=new Br(y),s.observe(document,{childList:!0,subtree:!0}),y();let E=!1;function S(e){throw E||(E=!0,ze("freeze-element "+n)),new _r(e)}function $(e,t,r,n){let o=new qr,{body:s}=Ae(o.parseFromString(e,"text/html")),i=j(Ae(s).childNodes,t,r,n);return Ae(i).map((e=>{switch(Ae(e).nodeType){case Nr:return Ae(e).outerHTML;case Ir:return Ae(e).textContent;default:return""}})).join("")}function j(e,t,r,n){let o=Ae([]);for(let s of e)T(s,t,r,n)&&o.push(s);return o}function T(e,t,r,n){let o=n.shouldAbort,s=n.regexExceptions,i=n.exceptionSelectors,a=n.rid;if("string"==typeof e){let i=e;return!!b(i,s)||(Ge()&&v(i,t,r,n),o&&S(a),Ge())}let c=e;switch(Ae(c).nodeType){case Nr:return!!function(e,t){if(t){let r=Ae(e);for(let e of t)if(r.matches(e))return!0}return!1}(c,i)||(o&&(Ge()&&v(c,t,r,n),S(a)),!!Ge()&&(Lr(c),v(c,t,r,n),!0));case Ir:return!!b(Ae(c).textContent,s)||(Ge()&&v(c,t,r,n),o&&S(a),!1);default:return!0}}function x(e,t,r,n){let s=Xr(e,t)||{},a=s.get&&i(s.get,e)||s.value;if(a)return{get:()=>function(...e){if(r(this)){let r=n(this);if(r){let n=e[0];if(!T(n,this,t,r))return n}}return o(a,this,e)}}}function R(e,t,r,n){let s=Xr(e,t)||{},a=s.get&&i(s.get,e)||s.value;if(a)return{get:()=>function(...e){if(!r(this))return o(a,this,e);let s=n(this);if(!s)return o(a,this,e);let i=j(e,this,t,s);return i.length>0?o(a,this,i):void 0}}}function k(e,t,r,n){let s=Xr(e,t)||{},a=s.get&&i(s.get,e)||s.value;if(a)return{get:()=>function(...e){let[s,c]=e,l="afterbegin"===s||"beforeend"===s;if(r(this,l)){let e=n(this,l);if(e){let r,n=l?this:Ae(this).parentNode;switch(t){case"insertAdjacentElement":if(!T(c,n,t,e))return c;break;case"insertAdjacentHTML":return r=$(c,n,t,e),r?i(a,this,s,r):void 0;case"insertAdjacentText":if(!T(c,n,t,e))return}}}return o(a,this,e)}}}function P(e,t,r,n){let o=Xr(e,t)||{},{set:s}=o;if(s)return{set(e){if(!r(this))return i(s,this,e);let o=n(this);if(!o)return i(s,this,e);let a=$(e,this,t,o);return a?i(s,this,a):void 0}}}function A(e,t,r,n){let o=Xr(e,t)||{},{set:s}=o;if(s)return{set(e){if(!r(this))return i(s,this,e);let o=n(this);return o?T(e,this,t,o)?i(s,this,e):void 0:i(s,this,e)}}}},"hide-if-canvas-contains":function(e,t="canvas",r=""){const n=Ze("hide-if-canvas-contains"),s=Xe(arguments),{mark:i,end:a}=Fe("hide-if-canvas-contains");if(!e)return void n("error","The parameter 'search' is required");if(!tn){i();const p=Ur.prototype;function u(e){const t=p[e];let r=l(t,(function(r,...n){const s=this.canvas;if(nn.has(s))return o(t,this,[r,...n]);const i=((rn.get(s)||"")+r).slice(-1e4);rn.set(s,i);for(const[t,r]of tn)t.test(i)&&cn(s,r,e,i);return o(t,this,[r,...n])}));st(r,t),Qr.defineProperty(window.CanvasRenderingContext2D.prototype,e,{value:r})}function f(){const e=p.clearRect;let t=l(e,(function(...t){let r=!1,n=!0;for(const{clearRectBehavior:e}of tn.values())"always"===e&&(r=!0),"never"!==e&&(n=!1);if(!n){const[e,n,o,s]=t,i=e<=0&&n<=0&&o>=this.canvas.width&&s>=this.canvas.height;(r||i)&&rn.delete(this.canvas)}return o(e,this,t)}));st(t,e),Qr.defineProperty(window.CanvasRenderingContext2D.prototype,"clearRect",{value:t})}function d(){const e=p.drawImage;let t=l(e,(function(t,...r){if(n("info","drawImage called with arguments:",t,...r),t&&"string"==typeof t.src&&t.src)for(const[e,r]of tn)e.test(t.src)&&cn(this.canvas,r,"drawImage",t.src);return o(e,this,[t,...r])}));st(t,e),Qr.defineProperty(window.CanvasRenderingContext2D.prototype,"drawImage",{value:t})}n("info","CanvasRenderingContext2D proxied"),u("fillText"),u("strokeText"),f(),d(),tn=new Gr;new Kr((e=>{for(let t of Ae(e))"childList"===t.type&&on.forEach((e=>{const t=Ae(e.canvasElement).closest(e.rule.selector);if(t&&!sn.has(t)){Lr(t),sn.add(t),on.delete(e),Ze("hide-if-canvas-contains")("success","Matched: ",t,`\nFILTER: hide-if-canvas-contains ${e.rule.formattedArguments}`);const r="hide-if-canvas-contains "+e.rule.formattedArguments;an.has(r)||(an.add(r),ze(r))}}))})).observe(Vr,{childList:!0,subtree:!0}),a()}const c=Be(e);tn.set(c,{selector:t,formattedArguments:s,clearRectBehavior:r})},"hide-if-shadow-contains":function(e,t="*"){const r=Xe(arguments);let n=`${e}\\${t}`;wn.has(n)||wn.set(n,[Be(e),t,Qe,r]);const s=Ze("hide-if-shadow-contains"),{mark:i,end:a}=Fe("hide-if-shadow-contains");if(!vn){vn=new pn((e=>{i();let t=new fn;for(let{target:r}of Ae(e)){let e=Ae(r).parentNode;for(;e;)[r,e]=[e,Ae(r).parentNode];if(!yn.has(r)&&!t.has(r)){t.add(r);for(let[e,t,n,o]of wn.values())if(e.test(Ae(r).textContent)){let e=Ae(r.host).closest(t);if(e){n(),Ae(r).appendChild(document.createElement("style")).textContent=":host {display: none !important}",Lr(e),yn.add(r),s("success","Hiding: ",e,`\nFILTER: hide-if-shadow-contains ${o}`);const t="hide-if-shadow-contains "+o;mn.has(t)||(mn.add(t),ze(t))}a()}}}}));let e=l(gn,(function(){let e=o(gn,this,arguments);return s("info","attachShadow is called for: ",e),vn.observe(e,{childList:!0,characterData:!0,subtree:!0}),e}));st(e,gn),un.defineProperty(hn,"attachShadow",{value:e})}},"json-override":function(e,t,r="",n=""){if(!e)throw new Rn("[json-override snippet]: Missing paths to override.");if(void 0===t)throw new Rn("[json-override snippet]: No value to override with.");let s=Ze("json-override");const{mark:i,end:a}=Fe("json-override");if(!Ln){function f(e,t){for(let{formattedArgs:r,prune:n,jsonPathObjects:o,needle:i,filter:a,value:c}of Ln.values())if(!a||a.test(t)){if(Ae(i).some((t=>!kt(e,t))))return e;for(let t of n)if(t.startsWith("jsonpath("))try{const n=o.get(t);n.evaluate(e).forEach((({parent:e,key:t})=>{s("success",`JSONPath match found at [${t}], replaced with ${c}`,`\nFILTER: json-override ${r}`),Nn("json-override "+r),e[t]=At(c)}))}catch(e){s("error",`JSONPath evaluation failed for: ${t}. Error: ${e.message}`)}else t.includes("{}")||t.includes("[]")?d(e,t,c,r):h(e,t,c,r)}return e}function d(e,t,r,n){let o=Ae(t).split("."),i=e;for(let e=0;e<o.length;e++){let a=o[e];if("[]"===a)return void(xn.isArray(i)&&(s("info",`Iterating over array at: ${a}`),Ae(i).forEach((t=>{null!=t&&d(t,o.slice(e+1).join("."),r,n)}))));if("{}"===a)return void(i&&"object"==typeof i&&(s("info",`Iterating over object at: ${a}`),An.keys(i).forEach((t=>{let s=i[t];null!=s&&d(s,o.slice(e+1).join("."),r,n)}))));if(!i||"object"!=typeof i||!m(i,a))return;e===o.length-1?(s("success",`Found ${t}, replaced it with ${r}`,`\nFILTER: json-override ${n}`),Nn("json-override "+n),i[a]=At(r)):i=i[a]}}function h(e,t,r,n){let o=kt(e,t);void 0!==o&&(s("success",`Found ${t}, replaced it with ${r}`,`\nFILTER: json-override ${n}`),Nn("json-override "+n),o[0][o[1]]=At(r))}i();let{parse:g}=kn;Ln=new Pn;let y=l(g,(function(e){return f(o(g,this,arguments),e)}));st(y,g),An.defineProperty(window.JSON,"parse",{value:y}),s("info","Wrapped JSON.parse for override");let{json:w}=On.prototype;An.defineProperty(window.Response.prototype,"json",{value:l(w,(function(e){return o(w,this,arguments).then((t=>f(t,e)))}))}),s("info","Wrapped Response.json for override"),a()}const c=Xe(arguments),p=Ae(e).split(/ +/),u=new Pn;for(const v of p)if(v.startsWith("jsonpath("))try{u.set(v,new Tn(v.slice(9,-1)))}catch(b){s("error",`Invalid JSONPath query: ${v}. Error: ${b.message}`)}Ln.set(e,{formattedArgs:c,prune:p,jsonPathObjects:u,needle:r.length?Ae(r).split(/ +/):[],filter:n?Be(n):null,value:t})},"json-prune":function(e,t="",r=""){if(!e)throw new Cn("Missing paths to prune");let n=Ze("json-prune");const{mark:s,end:i}=Fe("json-prune");if(!qn){function u(e){for(let{prune:t,needle:r,jsonPathObjects:o,stackNeedle:s,formattedArgs:i}of qn.values()){if(Ae(r).length>0&&Ae(r).some((t=>!kt(e,t))))return e;if(Ae(s)&&Ae(s).length>0&&!Ot(s,n))return e;for(let r of t)if(r.startsWith("jsonpath("))try{const t=o.get(r);t.evaluate(e).forEach((({parent:e,key:t})=>{n("success",`JSONPath match found and deleted at [${t}]`,`\nFILTER: json-prune ${i}`),Bn("json-prune "+i),delete e[t]}))}catch(e){n("error",`JSONPath evaluation failed for: ${r}. Error: ${e.message}`)}else r.includes("{}")||r.includes("[]")||r.includes("{-}")||r.includes("[-]")?f(e,r,i):h(e,r,i)}return e}function f(e,t,r){let o=Ae(t).split("."),s=e;for(let e=0;e<o.length;e++){let i=o[e];if("[]"===i)return void(In.isArray(s)&&(n("info",`Iterating over array at: ${i}`),Ae(s).forEach((t=>f(t,o.slice(e+1).join("."),r)))));if("[-]"===i){if(In.isArray(s)){n("info",`Iterating over array with element removal at: ${i}`);let t=o.slice(e+1).join("."),a=[];Ae(s).forEach(((e,r)=>{d(e,t)&&a.push(r)}));for(let e=a.length-1;e>=0;e--)n("success",`Found element at index ${a[e]} matching ${t} and removed entire element, \nFILTER: json-prune ${r}`),Bn("json-prune "+r),s.splice(a[e],1)}return}if("{}"===i)return void("object"==typeof s&&null!==s&&(n("info",`Iterating over object at: ${i}`),Dn.keys(s).forEach((t=>f(s[t],o.slice(e+1).join("."),r)))));if("{-}"===i){if("object"==typeof s&&null!==s){n("info",`Iterating over object with element removal at: ${i}`);let t=o.slice(e+1).join("."),a=[];Dn.keys(s).forEach((e=>{d(s[e],t)&&a.push(e)})),a.forEach((e=>{n("success",`Found object key ${e} matching ${t} and removed entire element, \nFILTER: json-prune ${r}`),Bn("json-prune "+r),delete s[e]}))}return}if(!s||"object"!=typeof s||!m(s,i))return;e===o.length-1?(n("success",`Found ${t} and deleted, \nFILTER: json-prune ${r}`),Bn("json-prune "+r),delete s[i]):s=s[i]}}function d(e,t){if(!t||""===t)return!0;let r=Ae(t).split("."),n=e;for(let e=0;e<r.length;e++){let t=r[e];if("[]"===t)return!!In.isArray(n)&&Ae(n).some((t=>d(t,r.slice(e+1).join("."))));if("{}"===t)return"object"==typeof n&&null!==n&&Dn.keys(n).some((t=>d(n[t],r.slice(e+1).join("."))));if(!n||"object"!=typeof n||!m(n,t))return!1;if(e===r.length-1)return!0;n=n[t]}return!1}function h(e,t,r){let o=kt(e,t);void 0!==o&&(n("success",`Found ${t} and deleted`,`\nFILTER: json-prune ${r}`),Bn("json-prune "+r),delete o[0][o[1]])}s();let{parse:g}=Wn;qn=new Fn;let y=l(g,(function(){return u(o(g,this,arguments))}));st(y,g),Dn.defineProperty(window.JSON,"parse",{value:y}),n("info","Wrapped JSON.parse for prune");let{json:w}=Hn.prototype,v=l(w,(function(){return o(w,this,arguments).then((e=>u(e)))}));st(v,w),Dn.defineProperty(window.Response.prototype,"json",{value:v}),n("info","Wrapped Response.json for prune"),i()}const a=Xe(arguments),c=Ae(e).split(/ +/),p=new Fn;for(const b of c)if(b.startsWith("jsonpath("))try{p.set(b,new Tn(b.slice(9,-1)))}catch(E){n("error",`Invalid JSONPath query: ${b}. Error: ${E.message}`)}qn.set(e,{formattedArgs:a,prune:c,jsonPathObjects:p,needle:t.length?Ae(t).split(/ +/):[],stackNeedle:r.length?Ae(r).split(/ +/):[]})},"map-override":function(e,t,r="",n,s){if(!e)throw new zn("[map-override snippet]: Missing method to override.");if(!t)throw new zn("[map-override snippet]: Missing needle.");Un||(Un=new Xn);let a=Ze("map-override");const{mark:c,end:p}=Fe("map-override"),{set:u,get:f,has:d}=Xn.prototype,h=Xe(arguments);if("set"!==e||Un.has("set"))if("get"!==e||Un.has("get")){if("has"===e&&!Un.has("has")){c(),i(u,Un,"has",Ae([]));let e=l(d,(function(e){const t=i(f,Un,"has");for(const{needleRegex:r,retVal:n,stackNeedles:o}of t)if("string"==typeof e||"number"==typeof e){const t=e.toString();if(r.test(t)&&Ot(o,a))return a("success",`Map.has returned ${n} for key: ${t}\nFILTER: map-override ${h}`),Gn("map-override "+h),n}return o(d,this,arguments)}));st(e,d),_n.defineProperty(window.Map.prototype,"has",{value:e}),a("info","Wrapped Map.prototype.has"),p()}}else{c(),i(u,Un,"get",Ae([]));let e=l(f,(function(e){const t=i(f,Un,"get");for(const{needleRegex:r,retVal:n,stackNeedles:o}of t)if("string"==typeof e||"number"==typeof e){const t=e.toString();if(r.test(t)&&Ot(o,a))return a("success",`Map.get returned ${n} for key: ${t}\nFILTER: map-override ${h}`),Gn("map-override "+h),n}return o(f,this,arguments)}));st(e,f),_n.defineProperty(window.Map.prototype,"get",{value:e}),a("info","Wrapped Map.prototype.get"),p()}else{c(),i(u,Un,"set",Ae([]));let e=l(u,(function(e,t){const r=i(f,Un,"set");for(const{needleRegex:e,pathSegments:n,stackNeedles:o}of r)if(Kn(t,e,n)&&Ot(o,a))return a("success",`Map.set is ignored for value matching needle: ${e}\nFILTER: map-override ${h}`),Gn("map-override "+h),this;return o(u,this,arguments)}));st(e,u),_n.defineProperty(window.Map.prototype,"set",{value:e}),a("info","Wrapped Map.prototype.set"),p()}const g=Be(t);let y=[];n&&(y=n.split("."));let w=[];s&&(w=s.split(",").map((e=>e.trim())));const m=i(f,Un,e);let v;"get"===e?v=""===r?void 0:r:"has"===e&&(v="true"===r),m.push({needleRegex:g,retVal:v,pathSegments:y,stackNeedles:w}),i(u,Un,e,m)},"override-property-read":function(e,t,r){if(!e)throw new Qn("[override-property-read snippet]: No property to override.");if(void 0===t)throw new Qn("[override-property-read snippet]: No value to override with.");const n=Xe(arguments);let o=Ze("override-property-read");const{mark:s,end:i}=Fe("override-property-read");let a=At(t),c=!1;o("info",`Overriding ${e}.`);const l=!("false"===r);s(),St(window,e,{get:()=>(o("success",`${e} override done.`,"\nFILTER: override-property-read",n),c||(c=!0,ze("override-property-read "+n)),a),set(){}},l),i()},"prevent-element-src-loading":function(e,t){if(!e||"string"!=typeof e)throw new eo("[prevent-element-src-loading snippet]: tagName param must be a string.");if(!t)throw new eo("[prevent-element-src-loading snippet]: Missing search parameter.");if(e=Ae(e).toString().toLowerCase(),!Ae(["script","img","iframe","link"]).includes(e))throw new eo("[prevent-element-src-loading snippet]: tagName parameter is incorrect.");const r={script:"data:text/javascript;base64,KCk9Pnt9",img:"data:image/gif;base64,R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==",iframe:"data:text/html;base64,PGRpdj48L2Rpdj4=",link:"data:text/plain;base64,"},n={script:window.HTMLScriptElement,img:window.HTMLImageElement,iframe:window.HTMLIFrameElement,link:window.HTMLLinkElement}[e],o="link"===e?"href":"src",s="onerror",i=Ze("[prevent-element-src-loading snippet]"),a=Xe(arguments),c="prevent-element-src-loading "+a,{mark:l,end:p}=Fe("prevent-element-src-loading");l();const u=Be(t);if(io.push({tagName:e,searchRegex:u}),i("info",`Added filter rule\nFILTER: prevent-element-src-loading ${a}`),!co.has(e)){co.add(e);const t={apply:(e,t,n)=>{if(!n[0]||!n[1])return ro.apply(e,t,n);const s=t.nodeName.toLowerCase(),a=n[0].toLowerCase(),l=n[1];return a===o&&io.some((e=>s===e.tagName&&e.searchRegex.test(l)))?(so.add(t),i("success",`Replaced setAttribute for ${a}: ${l} → ${r[s]}`),ao.has(c)||(ao.add(c),ze(c)),ro.apply(e,t,[a,r[s]])):ro.apply(e,t,n)}};n.prototype.setAttribute=new Proxy(n.prototype.setAttribute,t),i("info","Wrapped setAttribute function");const s=to.getOwnPropertyDescriptor(n.prototype,o);if(!s)return;to.defineProperty(n.prototype,o,{enumerable:!0,configurable:!0,get(){return s.get.call(this)},set(e){const t=this.nodeName.toLowerCase();io.some((r=>t===r.tagName&&r.searchRegex.test(e)))?(so.add(this),i("success",`Replaced in src/href setter ${e} → ${r[t]}`),ao.has(c)||(ao.add(c),ze(c)),s.set.call(this,r[t])):s.set.call(this,e)}}),i("info","Wrapped src/href property setter")}if(1===io.length){const e=to.getOwnPropertyDescriptor(HTMLElement.prototype,s);if(!e)return;to.defineProperty(HTMLElement.prototype,s,{enumerable:!0,configurable:!0,get(){return e.get.call(this)},set(t){so.has(this)?(i("success",`Replaced in onerror setter ${t} → () => {}`),ao.has(c)||(ao.add(c),ze(c)),e.set.call(this,(()=>{}))):e.set.call(this,t)}}),i("info","Wrapped onerror property setter");const t={apply:(e,t,r)=>{if(!r[0]||!r[1]||!t)return ro.apply(e,t,r);const n=r[0];return"function"==typeof t.getAttribute&&so.has(t)&&"error"===n?(i("success",`Replaced error event handler on ${t} with () => {}`),ao.has(c)||(ao.add(c),ze(c)),ro.apply(e,t,[n,()=>{}])):ro.apply(e,t,r)}};EventTarget.prototype.addEventListener=new Proxy(EventTarget.prototype.addEventListener,t),i("info","Wrapped addEventListener");(()=>{Zn("error",(e=>{const t=e.target;if(!t||!t.nodeName)return;const r=t.src||t.href,n=t.nodeName.toLowerCase();io.some((e=>n===e.tagName&&r&&e.searchRegex.test(r)))&&(t.onerror=()=>{})}),!0),i("info","Added event listener to defuse global errors")})()}p()},"prevent-listener":function(e,t,r){if(!e)throw new lo("[prevent-listener snippet]: No event type.");if(!wo){wo=new po;let e=Ze("[prevent]");const{mark:t,end:r}=Fe("prevent-listener");let n=l(yo,(function(n,s){t();for(let{evt:t,handlers:r,selectors:o,formattedArgs:a}of wo.values()){if(!t.test(n))continue;let c=this instanceof Element;for(let l=0;l<r.length;l++){const p=r[l],u=o[l];if(u&&(!c||!Ae(this).matches(u)))continue;if(p){const t=function(){try{const e=String("function"==typeof s?s:s.handleEvent);return p.test(e)}catch(t){return e("error","Error while trying to stringify listener: ",t),!1}};if(!function(){try{const e=i(ho,"function"==typeof s?s:s.handleEvent);return p.test(e)}catch(t){return e("error","Error while trying to stringify listener: ",t),!1}}()&&!t())continue}const f="prevent-listener "+a;return mo.has(f)||(mo.add(f),ze(f)),void(Ge()&&(fo.groupCollapsed("DEBUG [prevent] was successful",`\nFILTER: prevent-listener ${a}`),e("success",`type: ${n} matching ${t}`),e("success","handler:",s),p&&e("success",`matching ${p}`),u&&e("success","on element: ",this,` matching ${u}`),e("success","was prevented from being added"),fo.groupEnd()))}}return r(),o(yo,this,arguments)}));st(n,yo),uo.defineProperty(go,"addEventListener",{value:n}),e("info","Wrapped addEventListener")}const n=Xe(arguments);wo.has(e)||wo.set(e,{evt:Be(e),handlers:[],selectors:[],formattedArgs:n});let{handlers:s,selectors:a}=wo.get(e);s.push(t?Be(t):null),a.push(r)},profile:function(){We=!1},"replace-fetch-response":function(e,t="",r=null){const n=Xe(arguments),o=Ze("replace-fetch-response"),{mark:s,end:i}=Fe("replace-fetch-response");if(!e)return void o("error","The parameter 'search' is required");if(!jo){const e=e=>{s();return Ae(e).clone().text().then((t=>{let r=Ae(t);for(const[e,{replacement:t,needle:n,formattedArgs:s}]of jo){if(n){if(!Be(n).test(r)){Ge()&&(console.groupCollapsed(`DEBUG [replace-fetch-response] warn: '${n}' not found in fetch response`),o("warn",`${r}`),console.groupEnd());continue}Ge()&&(console.groupCollapsed(`DEBUG [replace-fetch-response] success: '${n}' found in fetch response`),o("info",`${r}`),console.groupEnd())}const i=r.toString();if(r=r.replace(e,t),r.toString()!==i){const n="replace-fetch-response "+s;Po.has(n)||(Po.add(n),ze(n)),Ge()&&(console.groupCollapsed(`DEBUG [replace-fetch-response] success: '${e}' replaced with '${t}' in fetch response`,`\nFILTER: replace-fetch-response ${s}`),o("success",`${r}`),console.groupEnd())}}if(r.toString()===t.toString())return e;const n=new ko(r.toString(),{status:e.status,statusText:e.statusText,headers:e.headers});return xo.defineProperties(n,{ok:{value:e.ok},redirected:{value:e.redirected},type:{value:e.type},url:{value:e.url}}),i(),n}))};jo=new To,o("info","Network API proxied"),a=e,So.push(a),$o()}var a;const c=Be(e),l=new Ro(c,"g");jo.set(l,{replacement:t,needle:r,formattedArgs:n})},"replace-outbound-value":function(e,t="",r="",n="",s="",i=""){if(!e)throw new Ao("[replace-outbound-value snippet]: Missing method path.");let a=Ze("replace-outbound-value");const{mark:c,end:p}=Fe("replace-outbound-value"),u=Xe(arguments);let f=!1;function d(){f||(f=!0,ze("replace-outbound-value "+u))}function h(e,t,r,n){if("base64"===n)try{if(function(e){try{if(""===e)return!1;const t=Lo(e),r=Mo(t),n=Ae(e).replace(/=+$/,"").toString();return Ae(r).replace(/=+$/,"").toString()===n}catch(e){return!1}}(e)){const n=Lo(e);a("info",`Decoded base64 content: ${n}`);const o=t?Ae(n).replace(t,r).toString():n;a("info",o!==n?`Modified decoded content: ${o}`:"Decoded content was not modified");const s=Mo(o);return a("info",`Re-encoded to base64: ${s}`),s}a("info",`Content is plain text: ${e}`);const n=t?Ae(e).replace(t,r).toString():e;a("info",n!==e?`Modified plain text content: ${n}`:"Plain text content was not modified");const o=Mo(n);return a("info",`Encoded to base64: ${o}`),o}catch(t){return a("info",`Error processing base64 content: ${t.message}`),e}return t?Ae(e).replace(t,r).toString():e}function g(e,t,r,n,o,s){const i=r?new No(Be(r),"g"):null;if(t.length&&"object"==typeof e&&null!==e){const c=r?function(e,t,r,n,o){if(!t.length)return e;let s=e;for(let r=0;r<t.length-1;r++){if(!s||"object"!=typeof s)return a("info",`Cannot navigate to path: property '${t[r]}' not found`),e;s=s[t[r]]}const i=t[t.length-1];if(!s||"object"!=typeof s||!(i in s))return a("info",`Target property '${i}' not found at path`),e;const c=s[i];if("string"!=typeof c)return a("info","Property at path is not a string: "+typeof c),e;const l=h(c,r,n,o);if(l!==c){const r=JSON.parse(JSON.stringify(e));let n=r;for(let e=0;e<t.length-1;e++)n=n[t[e]];return n[i]=l,a("info",`Replaced value at path '${t.join(".")}': '${c}' -> '${l}'`),r}return e}(e,t,i,n,o):e;return c!==e&&(a("success",`Replaced outbound value\nFILTER: replace-outbound-value ${s}`),d()),c}if("string"==typeof e){r||a("info",`Original text content: ${e}`);const t=r?h(e,i,n,o):e;return t!==e&&(a("success",`Replaced outbound value: ${t} \nFILTER: replace-outbound-value ${s}`),d()),t}return e}c();const y=function(e,t){let r=e,n=Ae(t).split(".");for(let e=0;e<n.length-1;e++){let t=n[e];if(!r||"object"!=typeof r&&"function"!=typeof r)return{base:r,prop:t,remainingPath:n.slice(e).join("."),success:!1};r=r[t]}return{base:r,prop:n[n.length-1],success:!0}}(window,e);if(!y.success)return a("error",`Could not reach the end of the prop chain: ${e}. Remaining path: ${y.remainingPath}`),void p();const{base:w,prop:m}=y,v=w[m];if(!v||"function"!=typeof v)return a("error",`Could not retrieve the method: ${e}`),void p();let b=[];s&&(b=Ae(s).split("."));let E=[];i&&(E=Ae(i).split(",").map((e=>e.trim())));let S=!1,$=l(v,(function(){if(S)return o(v,this,arguments);S=!0;const e=o(v,this,arguments);if(E.length&&!Ot(E,a))return S=!1,e;if(e&&"function"==typeof e.then)return a("info","Method returned a Promise, modifying resolved value"),S=!1,e.then((e=>{const o="object"==typeof e?JSON.stringify(e):e;return a("info",`Promise resolved with value: ${o}`),g(e,b,t,r,n,s)})).catch((e=>{throw a("info",`Promise rejected: ${e.message}`),e}));const i=g(e,b,t,r,n,s);return S=!1,i}));st($,v),Oo.defineProperty(w,m,{value:$}),a("info",`Wrapped ${e}`),p()},"replace-xhr-request":function(e,t="",r=null,n="replace"){const o=Xe(arguments),s=Ze("replace-xhr-request"),{mark:i,end:a}=Fe("replace-xhr-request");if(!e)throw new _o("[replace-xhr-request]: Missing 'search' parameter");function c(e){try{return Xo.parse(e)}catch(t){return e}}function l(e,t,r){let n=e[t];zo.isArray(n)?zo.isArray(r)?e[t]=Ae(n).concat(r):Ae(n).push(r):"object"!=typeof n||null===n||"object"!=typeof r||null===r||zo.isArray(r)?e[t]="string"==typeof n?n+Ae(r).toString():r:Uo.assign(n,r)}var p;if(Bo||(Bo=new Map,s("info","XMLHttpRequest proxied"),p=e=>{i();let t=e;for(const[r,{replacement:n,needle:o,formattedArgs:i,isJsonPath:a,jsonPathEngine:p,mode:u}]of Bo){if(o){if(!Be(o).test(t))continue;s("info",`'${o}' found in XHR request body`)}if(a)try{let e=Xo.parse(t);const r=p.evaluate(e);Ae(r).forEach((({parent:e,key:t})=>{let r=c(n);"append"===u?l(e,t,r):e[t]=r,s("success",`JSONPath [${u}] at [${t}] with `+n,"\nFILTER: replace-xhr-request "+i);const o="replace-xhr-request "+i;Go.has(o)||(Go.add(o),ze(o))})),t=Xo.stringify(e)}catch(e){s("info","JSONPath: skipping non-JSON body or evaluation error: "+e.message)}else if(t=Ae(t).replace(r,n).toString(),e.toString()!==t.toString()){s("success",`'${r}' replaced with '${n}' in XHR request body`,"\nFILTER: replace-xhr-request "+i);const e="replace-xhr-request "+i;Go.has(e)||(Go.add(e),ze(e))}}return a(),t},Do.push(p),Jo()),Ae(e).startsWith("jsonpath(")){let i;try{const t=Ae(e).slice(9,-1).toString();i=new Tn(t)}catch(t){return void s("error",`Invalid JSONPath query: ${e}. Error: ${t.message}`)}Bo.set(e,{replacement:t,needle:r,formattedArgs:o,isJsonPath:!0,jsonPathEngine:i,mode:n})}else{const s=Be(e),i=new Vo(s,"g");Bo.set(i,{replacement:t,needle:r,formattedArgs:o,isJsonPath:!1,jsonPathEngine:null,mode:n})}},"replace-xhr-response":function(e,t="",r=null){const n=Xe(arguments),o=Ze("replace-xhr-response"),{mark:s,end:i}=Fe("replace-xhr-response");var a;if(e)if(Ko||(Ko=new Map,o("info","XMLHttpRequest proxied"),a=e=>{s();let t=e;for(const[r,{replacement:n,needle:s,formattedArgs:i,isJsonPath:a,jsonPathEngine:c}]of Ko){if(s){if(!Be(s).test(t)){Ge()&&(console.groupCollapsed(`DEBUG [replace-xhr-response] warn: '${s}' not found in XHR response`),o("warn",t),console.groupEnd());continue}Ge()&&(console.groupCollapsed(`DEBUG [replace-xhr-response] success: '${s}' found in XHR response`),o("info",t),console.groupEnd())}if(a)try{let e=Qo.parse(t);const r=c.evaluate(e);Ae(r).forEach((({parent:e,key:t})=>{e[t]=At(n),o("success",`JSONPath match at [${t}], replaced with `+n,"\nFILTER: replace-xhr-response "+i);const r="replace-xhr-response "+i;Zo.has(r)||(Zo.add(r),ze(r))})),t=Qo.stringify(e)}catch(e){o("info","JSONPath: skipping non-JSON response or evaluation error: "+e.message)}else if(t=Ae(t).replace(r,n).toString(),e.toString()!==t.toString()){const e="replace-xhr-response "+i;Zo.has(e)||(Zo.add(e),ze(e)),Ge()&&(console.groupCollapsed(`DEBUG [replace-xhr-response] success: '${r}' replaced with '${n}' in XHR response`,"\nFILTER: replace-xhr-response "+i),o("success",t),console.groupEnd())}}return i(),t.toString()},Ho.push(a),Jo()),Ae(e).startsWith("jsonpath(")){let s;try{const t=Ae(e).slice(9,-1).toString();s=new Tn(t)}catch(t){return void o("error",`Invalid JSONPath query: ${e}. Error: ${t.message}`)}Ko.set(e,{replacement:t,needle:r,formattedArgs:n,isJsonPath:!0,jsonPathEngine:s})}else{const o=Be(e),s=new Yo(o,"g");Ko.set(s,{replacement:t,needle:r,formattedArgs:n,isJsonPath:!1,jsonPathEngine:null})}else o("error","The parameter 'pattern' is required")},"strip-fetch-query-parameter":function(e,t=null){const r=Xe(arguments),n=Ze("strip-fetch-query-parameter"),{mark:o,end:s}=Fe("strip-fetch-query-parameter"),i=e=>{o();for(let[t,r]of es.entries()){const{reg:o,args:s}=r;if((!o||o.test(e))&&rs(e.searchParams,t)){n("success",`${t} has been stripped from url ${e}`,`\nFILTER: strip-fetch-query-parameter ${s}`);const r="strip-fetch-query-parameter "+s;ns.has(r)||(ns.add(r),ze(r)),ts(e.searchParams,t)}}s()};var a;es||(es=new Map,a=i,Eo.push(a),$o()),es.set(e,{reg:t&&Be(t),args:r})},"timer-override":function(e,t="",r="",n=us.BOTH,s=""){if(!e)throw new os("[timer-override snippet]: Missing required parameter timerValue.");if(!ss.values(us).includes(n))throw new os("[timer-override snippet]: Invalid mode. Acceptable values are: "+ss.values(us).join(", "));const a=is(e,10);if(as(a))throw new os("[timer-override snippet]: timerValue must be a number.");if(!fs){fs=Ae([]);const p=Ze("timer-override"),{mark:u,end:f}=Fe("timer-override");function d(e){try{return"function"==typeof e?i(cs,e):""+e}catch(e){return""}}function h(e,t,r,n,s,i,a){const c=d(s);for(const l of fs){if(n.indexOf(l.mode)<0)continue;if(l.needleRegex){const e=""+i;if(!l.needleRegex.test(c)&&!l.needleRegex.test(e))continue;p("info",l.needle+" found in "+c)}if(l.stackNeedles.length>0&&!Ot(l.stackNeedles,p))continue;let u=s;const f=l.newDelay;l.isNoop&&(u=()=>{},p("success","Callback replaced with noop for "+c)),p("success",r+" replaced with "+f+" for "+c);const d="timer-override "+l.formattedArgs;ds.has(d)||(ds.add(d),ze(d));const h=Ae([u,f]);for(let e=2;e<a.length;e++)h.push(a[e]);return o(t,e,h)}return null}u();const g=Ae([us.TIMEOUT,us.BOTH]);let y=l(ls,(function(e,t){const r=h(this,ls,"setTimeout",g,e,t,arguments);return null!==r?r:o(ls,this,arguments)}));st(y,ls),ss.defineProperty(window,"setTimeout",{value:y});const w=Ae([us.INTERVAL,us.BOTH]);let m=l(ps,(function(e,t){const r=h(this,ps,"setInterval",w,e,t,arguments);return null!==r?r:o(ps,this,arguments)}));st(m,ps),ss.defineProperty(window,"setInterval",{value:m}),p("info","timer APIs proxied"),f()}let c=[];s&&(c=s.split(/ +/)),fs.push({newDelay:a,needle:t,needleRegex:t?Be(t):null,mode:n,isNoop:"noop"===r,stackNeedles:c,formattedArgs:Xe(arguments)})},trace:function(...e){o(Ye,null,e)}};
const snippets=hs;
let context;
for (const [name, ...args] of filters) {
if (snippets.hasOwnProperty(name)) {
try { context = snippets[name].apply(context, args); }
catch (error) { console.error(error); }
}
}
context = void 0;
};
const graph = new Map([["abort-current-inline-script",null],["abort-on-iframe-property-read",null],["abort-on-iframe-property-write",null],["abort-on-property-read",null],["abort-on-property-write",null],["array-override",null],["blob-override",null],["cookie-remover",null],["debug",null],["event-override",null],["freeze-element",null],["hide-if-canvas-contains",null],["hide-if-shadow-contains",null],["json-override",null],["json-prune",null],["map-override",null],["override-property-read",null],["prevent-element-src-loading",null],["prevent-listener",null],["profile",null],["replace-fetch-response",null],["replace-outbound-value",null],["replace-xhr-request",null],["replace-xhr-response",null],["strip-fetch-query-parameter",null],["timer-override",null],["trace",null]]);
callback.get = snippet => graph.get(snippet);
callback.has = snippet => graph.has(snippet);
callback.getGraph = () => graph;
callback.setEnvironment = env => {
  if (typeof currentEnvironment !== "undefined")
    currentEnvironment = env;
};
callback.setDebugStyle = styles => {
  if (typeof currentEnvironment !== "undefined")
  {
    delete currentEnvironment.initial;
    currentEnvironment.debugCSSProperties = styles;
  }
    
};
callback.getEnvironment = () => currentEnvironment;
/* harmony default export */ const main = (callback);
;// ./src/content/shared/constants.js
/*
 * This file is part of eyeo's Web Extension Ad Blocking Toolkit (EWE),
 * Copyright (C) 2006-present eyeo GmbH
 *
 * EWE is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 3 as
 * published by the Free Software Foundation.
 *
 * EWE is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with EWE.  If not, see <http://www.gnu.org/licenses/>.
 */

/**
 * Prefix that should be used for storage and synchronization to avoid conflicts
 * when multiple extensions are installed in the same session.
 *
 * !!! IMPORTANT - DO NOT CHANGE THIS VALUE !!!
 * This exact string "ab" is hardcoded in the build
 * configurations and is replaced during the build process with host-specific
 * values (e.g., "ab" for Adblock, "abp" for Adblock Plus).
 *
 * If you change this value, the build process will NOT replace it, and the
 * extension will fail to work properly due to namespace conflicts.
 *
 * Build configuration references:
 * - host/adblock/build/config/base.mjs (replacements.search)
 * - host/adblockplus/build/webext/config/base.mjs (replacements.search)
 *
 * @type {string}
 */
const HOST_PREFIX_TO_REPLACE = "ab";

/**
 * Dataset key used to exchange the communication channel name between content
 * scripts in different contexts (main world and isolated world)
 * @type {string}
 */
const COMMS_CHANNEL_DATASET_KEY = `${HOST_PREFIX_TO_REPLACE}FiltersChannel`;

/**
 * Event used to communicate between content script contexts
 * @type {string}
 */
const HANDSHAKE_EVENT_NAME = `${HOST_PREFIX_TO_REPLACE}-handshake`;

/**
 * Storage key used to cache the filters config in content scripts
 * @type {string}
 */
const CACHED_FILTERS_CONFIG_KEY = `${HOST_PREFIX_TO_REPLACE}-filters-config`;

/**
 * CSS properties applied to elements hidden in debug mode
 * @type {string[][]}
 */
const DEBUG_CSS_PROPERTIES = [
  ["background", "repeating-linear-gradient(to bottom, #e67370 0, #e67370 9px, white 9px, white 10px)"],
  ["outline", "solid red"]
];

;// ./src/content/main/shims/storage.js
/*
 * This file is part of eyeo's Web Extension Ad Blocking Toolkit (EWE),
 * Copyright (C) 2006-present eyeo GmbH
 *
 * EWE is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 3 as
 * published by the Free Software Foundation.
 *
 * EWE is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with EWE.  If not, see <http://www.gnu.org/licenses/>.
 */

/* eslint-disable no-extend-native */

function shimStorage(CACHED_FILTERS_CONFIG_KEY) {
  // =================== Secured copies of native functions ====================
  // These are captured before page scripts run.
  // Used inside Proxy apply handlers which run after page scripts.
  const {parse: $JSONparse, stringify: $JSONstringify} = JSON;
  const {keys: $ObjectKeys} = Object;
  const {
    apply: $ReflectApply,
    ownKeys: $ReflectOwnKeys,
    get: $ReflectGet,
    set: $ReflectSet,
    has: $ReflectHas,
    getOwnPropertyDescriptor: $ReflectGetOwnPropertyDescriptor,
    defineProperty: $ReflectDefineProperty,
    deleteProperty: $ReflectDeleteProperty
  } = Reflect;
  const {filter: $ArrayFilter} = Array.prototype;
  const {get: $MapGet, set: $MapSet, has: $MapHas} = Map.prototype;
  const $String = String;

  // Helpers using secured copies
  const filter = (arr, fn) => $ReflectApply($ArrayFilter, arr, [fn]);
  const mapGet = (map, key) => $ReflectApply($MapGet, map, [key]);
  const mapSet = (map, key, val) => $ReflectApply($MapSet, map, [key, val]);
  const mapHas = (map, key) => $ReflectApply($MapHas, map, [key]);

  // Need to unwrap our own proxies when multiple extensions run this shim.
  const realLocalStorage = window.localStorage;
  const realSessionStorage = window.sessionStorage;
  let localStorageProxy;
  let sessionStorageProxy;
  function unwrapStorage(storage) {
    if (storage === localStorageProxy) {
      return realLocalStorage;
    }
    if (storage === sessionStorageProxy) {
      return realSessionStorage;
    }
    return storage;
  }

  const originalToStrings = new Map();

  const storageGetItemDesc = Object.getOwnPropertyDescriptor(
    Storage.prototype, "getItem"
  );
  const originalStorageGetItem = storageGetItemDesc.value;

  // =================== Conditional application of the shim ===================
  function shouldShimStorage() {
    const config = getConfig(window.sessionStorage) ||
      getConfig(window.localStorage);
    return Boolean(config);
  }

  if (!shouldShimStorage()) {
    return;
  }

  // ===================== Storage.prototype.getItem ======================
  // @docs https://developer.mozilla.org/en-US/docs/Web/API/Storage/getItem
  function getConfig(storage) {
    try {
      const configSerialized = $ReflectApply(
        originalStorageGetItem, unwrapStorage(storage),
        [CACHED_FILTERS_CONFIG_KEY]
      );
      if (configSerialized) {
        return $JSONparse(configSerialized);
      }
    }
    catch (e) {
      // If we can't parse, return null
    }
    return null;
  }

  function websiteHasValue(config) {
    return config && typeof config.websiteValue === "string";
  }
  const storageGetItemProxy = new Proxy(originalStorageGetItem, {
    apply(target, thisArg, argumentsList) {
      const key = argumentsList[0];
      const unwrappedThis = unwrapStorage(thisArg);
      if (key === CACHED_FILTERS_CONFIG_KEY) {
        const config = getConfig(unwrappedThis);
        if (websiteHasValue(config)) {
          return config.websiteValue;
        }
        return null;
      }
      return $ReflectApply(target, unwrappedThis, argumentsList);
    }
  });
  Object.defineProperty(Storage.prototype, "getItem", {
    ...storageGetItemDesc,
    value: storageGetItemProxy
  });
  mapSet(
    originalToStrings,
    storageGetItemProxy,
    originalStorageGetItem.toString.bind(originalStorageGetItem)
  );

  // ===================== Storage.prototype.setItem ===========================
  // @docs https://developer.mozilla.org/en-US/docs/Web/API/Storage/setItem
  const storageSetItemDesc = Object.getOwnPropertyDescriptor(
    Storage.prototype, "setItem"
  );
  const originalStorageSetItem = storageSetItemDesc.value;
  const storageSetItemProxy = new Proxy(originalStorageSetItem, {
    apply(target, thisArg, argumentsList) {
      const key = argumentsList[0];
      const unwrappedThis = unwrapStorage(thisArg);
      if (key === CACHED_FILTERS_CONFIG_KEY) {
        const config = getConfig(unwrappedThis) || {};
        config.websiteValue = $String(argumentsList[1]);
        $ReflectApply(
          target,
          unwrappedThis,
          [CACHED_FILTERS_CONFIG_KEY, $JSONstringify(config)]
        );
        return void 0;
      }
      return $ReflectApply(target, unwrappedThis, argumentsList);
    }
  });
  Object.defineProperty(Storage.prototype, "setItem", {
    ...storageSetItemDesc,
    value: storageSetItemProxy
  });
  mapSet(
    originalToStrings,
    storageSetItemProxy,
    originalStorageSetItem.toString.bind(originalStorageSetItem)
  );

  // ================== Storage.prototype.removeItem ==========================
  // @docs https://developer.mozilla.org/en-US/docs/Web/API/Storage/removeItem
  const storageRemoveItemDesc = Object.getOwnPropertyDescriptor(
    Storage.prototype, "removeItem"
  );
  const originalStorageRemoveItem = storageRemoveItemDesc.value;
  const storageRemoveItemProxy = new Proxy(originalStorageRemoveItem, {
    apply(target, thisArg, argumentsList) {
      const key = argumentsList[0];
      const unwrappedThis = unwrapStorage(thisArg);
      if (key === CACHED_FILTERS_CONFIG_KEY) {
        const config = getConfig(unwrappedThis);
        if (websiteHasValue(config)) {
          delete config.websiteValue;
          $ReflectApply(
            originalStorageSetItem,
            unwrappedThis, [CACHED_FILTERS_CONFIG_KEY, $JSONstringify(config)]
          );
        }
        return void 0;
      }
      return $ReflectApply(target, unwrappedThis, argumentsList);
    }
  });
  Object.defineProperty(Storage.prototype, "removeItem", {
    ...storageRemoveItemDesc,
    value: storageRemoveItemProxy
  });
  mapSet(
    originalToStrings,
    storageRemoveItemProxy,
    originalStorageRemoveItem.toString.bind(originalStorageRemoveItem)
  );

  // ==================== Storage.prototype.clear ============================
  // @docs https://developer.mozilla.org/en-US/docs/Web/API/Storage/clear
  const storageClearDesc = Object.getOwnPropertyDescriptor(
    Storage.prototype, "clear"
  );
  const originalStorageClear = storageClearDesc.value;
  const storageClearProxy = new Proxy(originalStorageClear, {
    apply(target, thisArg, argumentsList) {
      const unwrappedThis = unwrapStorage(thisArg);
      const config = getConfig(unwrappedThis);
      if (config) {
        delete config.websiteValue;
      }

      $ReflectApply(target, unwrappedThis, argumentsList);

      // Restore our config (without websiteValue)
      if (config && $ObjectKeys(config).length > 0) {
        $ReflectApply(
          originalStorageSetItem,
          unwrappedThis, [CACHED_FILTERS_CONFIG_KEY, $JSONstringify(config)]
        );
      }
      return void 0;
    }
  });
  Object.defineProperty(Storage.prototype, "clear", {
    ...storageClearDesc,
    value: storageClearProxy
  });
  mapSet(
    originalToStrings,
    storageClearProxy,
    originalStorageClear.toString.bind(originalStorageClear)
  );

  // ===================== Storage.prototype.key ===============================
  // @docs https://developer.mozilla.org/en-US/docs/Web/API/Storage/key
  const storageKeyDesc = Object.getOwnPropertyDescriptor(
    Storage.prototype, "key"
  );
  const originalStorageKey = storageKeyDesc.value;
  const storageKeyProxy = new Proxy(originalStorageKey, {
    apply(target, thisArg, argumentsList) {
      const unwrappedThis = unwrapStorage(thisArg);
      const config = getConfig(unwrappedThis);
      if (!config || websiteHasValue(config)) {
        return $ReflectApply(target, unwrappedThis, argumentsList);
      }

      const requestedIndex = argumentsList[0];
      for (let i = 0; i <= requestedIndex; i++) {
        const key = $ReflectApply(target, unwrappedThis, [i]);
        if (key === CACHED_FILTERS_CONFIG_KEY) {
          return $ReflectApply(target, unwrappedThis, [requestedIndex + 1]);
        }
      }
      return $ReflectApply(target, unwrappedThis, argumentsList);
    }
  });
  Object.defineProperty(Storage.prototype, "key", {
    ...storageKeyDesc,
    value: storageKeyProxy
  });
  mapSet(
    originalToStrings,
    storageKeyProxy,
    originalStorageKey.toString.bind(originalStorageKey)
  );

  // =================== Storage.prototype.length ============================
  // @docs https://developer.mozilla.org/en-US/docs/Web/API/Storage/length
  const storageLengthDesc = Object.getOwnPropertyDescriptor(
    Storage.prototype, "length"
  );
  const originalStorageLengthGetter = storageLengthDesc.get;
  Object.defineProperty(Storage.prototype, "length", {
    ...storageLengthDesc,
    get() {
      const unwrappedThis = unwrapStorage(this);
      const originalLength =
        $ReflectApply(originalStorageLengthGetter, unwrappedThis, []);
      const config = getConfig(unwrappedThis);
      if (config && !websiteHasValue(config)) {
        return originalLength - 1;
      }
      return originalLength;
    }
  });

  // ================== Proxy wrapper for localStorage ===========
  // Handles: {...localStorage}, Object.keys(), Object.values(), for...in, etc.
  const methodProxyCache = new Map();

  function getMethodProxy(storage, method) {
    if (mapHas(methodProxyCache, method)) {
      return mapGet(methodProxyCache, method);
    }
    const methodProxy = new Proxy(method, {
      apply(fn, _, args) {
        return $ReflectApply(fn, storage, args);
      }
    });
    mapSet(methodProxyCache, method, methodProxy);
    // Register toString for the wrapper to preserve function name
    const originalMethod = mapGet(originalToStrings, method);
    if (originalMethod) {
      mapSet(originalToStrings, methodProxy, originalMethod);
    }
    return methodProxy;
  }

  const storageInstanceProxyConfig = {
    ownKeys(target) {
      const keys = $ReflectOwnKeys(target);
      const config = getConfig(target);
      if (config && !websiteHasValue(config)) {
        return filter(keys, key => key !== CACHED_FILTERS_CONFIG_KEY);
      }
      return keys;
    },

    // Required for spread operator
    getOwnPropertyDescriptor(target, prop) {
      if (prop === CACHED_FILTERS_CONFIG_KEY) {
        const config = getConfig(target);
        if (config && !websiteHasValue(config)) {
          return void 0; // Hide the property entirely
        }
        // When website has set a value, return a proper enumerable descriptor
        // with the website's value (not our internal config)
        if (websiteHasValue(config)) {
          return {
            value: config.websiteValue,
            writable: true,
            enumerable: true,
            configurable: true
          };
        }
      }
      return $ReflectGetOwnPropertyDescriptor(target, prop);
    },

    // Needed for 'in' operator
    has(target, prop) {
      if (prop === CACHED_FILTERS_CONFIG_KEY) {
        const config = getConfig(target);
        if (config && !websiteHasValue(config)) {
          return false;
        }
      }
      return $ReflectHas(target, prop);
    },

    // Forward get/set using original target so native methods work correctly
    get(target, prop) {
      if (prop === CACHED_FILTERS_CONFIG_KEY) {
        return target.getItem(CACHED_FILTERS_CONFIG_KEY);
      }
      // Return correct toStringTag so Object.prototype.toString returns
      // [object Storage] instead of [object Object] (for older Firefox)
      if (prop === Symbol.toStringTag) {
        return "Storage";
      }
      const value = $ReflectGet(target, prop, target);
      // For methods, wrap in a proxy to bind `this` to original target
      // while preserving toString behavior
      if (typeof value === "function") {
        return getMethodProxy(target, value);
      }
      return value;
    },

    set(target, prop, value) {
      if (prop === CACHED_FILTERS_CONFIG_KEY) {
        target.setItem(CACHED_FILTERS_CONFIG_KEY, value);
        return true;
      }
      return $ReflectSet(target, prop, value, target);
    },

    defineProperty(target, prop, descriptor) {
      if (prop === CACHED_FILTERS_CONFIG_KEY) {
        if ("value" in descriptor) {
          target.setItem(CACHED_FILTERS_CONFIG_KEY, descriptor.value);
        }
        return true;
      }
      return $ReflectDefineProperty(target, prop, descriptor);
    },

    deleteProperty(target, prop) {
      if (prop === CACHED_FILTERS_CONFIG_KEY) {
        target.removeItem(CACHED_FILTERS_CONFIG_KEY);
        return true;
      }
      return $ReflectDeleteProperty(target, prop);
    }
  };

  localStorageProxy = new Proxy(
    window.localStorage,
    storageInstanceProxyConfig
  );

  Object.defineProperty(window, "localStorage", {
    value: localStorageProxy,
    writable: false,
    configurable: true,
    enumerable: true
  });

  sessionStorageProxy = new Proxy(
    window.sessionStorage,
    storageInstanceProxyConfig
  );

  Object.defineProperty(window, "sessionStorage", {
    value: sessionStorageProxy,
    writable: false,
    configurable: true,
    enumerable: true
  });

  // ===================== Function.prototype.toString =========================
  // @docs https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Function/toString
  const functionToStringDesc = Object.getOwnPropertyDescriptor(
    Function.prototype, "toString"
  );
  const originalFunctionToString = functionToStringDesc.value;
  const functionToStringProxy = new Proxy(originalFunctionToString, {
    apply(target, thisArg, argumentsList) {
      // Call "super" first, just in case the function was overwritten and had
      // checks if it was called
      const r = $ReflectApply(target, thisArg, argumentsList);

      const restoredToString = mapGet(originalToStrings, thisArg);
      if (restoredToString) {
        return $ReflectApply(restoredToString, thisArg, argumentsList);
      }

      return r;
    }
  });
  Object.defineProperty(Function.prototype, "toString", {
    ...functionToStringDesc,
    value: functionToStringProxy
  });
  mapSet(
    originalToStrings,
    functionToStringProxy,
    originalFunctionToString.toString.bind(originalFunctionToString)
  );
}

;// ./src/content/shared/helpers.js
/*
 * This file is part of eyeo's Web Extension Ad Blocking Toolkit (EWE),
 * Copyright (C) 2006-present eyeo GmbH
 *
 * EWE is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 3 as
 * published by the Free Software Foundation.
 *
 * EWE is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with EWE.  If not, see <http://www.gnu.org/licenses/>.
 */



/**
 * Claims a communication channel name from the document's dataset.
 *
 * If a channel name already exists in the dataset, it is consumed (removed
 * from the dataset and returned). If no channel name exists, the fallback
 * channel is stored in the dataset and returned.
 *
 * This mechanism ensures that only one content script can claim the
 * channel name at a time, preventing conflicts when the main world
 * and isolated world scripts execution order is not consistent.
 * @see https://developer.mozilla.org/en-US/docs/Mozilla/Firefox/Releases/139#changes_for_add-on_developers
 * @see https://bugzil.la/1792685
 * @see https://eyeo.atlassian.net/wiki/spaces/B2C/pages/1666678786/Content-script+based+snippets
 *
 * @param {string} fallbackChannel - The channel name to use and store if
 *   none is present.
 * @returns {string} The claimed channel name (either the existing one
 *   or the fallback).
 */
function claimCommsChannel(fallbackChannel) {
  let channelName = document.documentElement.dataset[COMMS_CHANNEL_DATASET_KEY];

  if (!channelName) {
    channelName = fallbackChannel;
    document.documentElement.dataset[COMMS_CHANNEL_DATASET_KEY] = channelName;
  }
  else {
    delete document.documentElement.dataset[COMMS_CHANNEL_DATASET_KEY];
  }

  return channelName;
}

;// ./src/all/errors.js
/*
 * This file is part of eyeo's Web Extension Ad Blocking Toolkit (EWE),
 * Copyright (C) 2006-present eyeo GmbH
 *
 * EWE is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 3 as
 * published by the Free Software Foundation.
 *
 * EWE is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with EWE.  If not, see <http://www.gnu.org/licenses/>.
 */

const ERROR_NO_CONNECTION = (/* unused pure expression or super */ null && ("Could not establish connection. " +
      "Receiving end does not exist."));
const ERROR_CLOSED_CONNECTION = (/* unused pure expression or super */ null && ("A listener indicated an asynchronous " +
      "response by returning true, but the message channel closed before a " +
      "response was received"));
// https://bugzilla.mozilla.org/show_bug.cgi?id=1578697
const ERROR_MANAGER_DISCONNECTED = "Message manager disconnected";

/**
 * Reconstructs an error from a serializable error object
 *
 * @param {Object} errorData - Error object
 *
 * @returns {Error} error
 */
function fromSerializableError(errorData) {
  const error = new Error(errorData.message);
  error.cause = errorData.cause;
  error.name = errorData.name;
  error.stack = errorData.stack;

  return error;
}

/**
 * Filters out `browser.runtime.sendMessage` errors to do with the receiving end
 * no longer existing.
 *
 * @param {Promise} promise The promise that should have "no connection" errors
 *   ignored. Generally this would be the promise returned by
 *   `browser.runtime.sendMessage`.
 * @return {Promise} The same promise, but will resolve with `undefined` instead
 *   of rejecting if the receiving end no longer exists.
 */
function ignoreNoConnectionError(promise) {
  return promise.catch(error => {
    if (typeof error == "object" &&
        (error.message == ERROR_NO_CONNECTION ||
         error.message == ERROR_CLOSED_CONNECTION ||
         error.message == ERROR_MANAGER_DISCONNECTED)) {
      return;
    }

    throw error;
  });
}

/**
 * Creates serializable error object from given error
 *
 * @param {Error} error - Error
 *
 * @returns {Object} serializable error object
 */
function toSerializableError(error) {
  return {
    cause: error.cause instanceof Error ?
      toSerializableError(error.cause) :
      error.cause,
    message: error.message,
    name: error.name,
    stack: error.stack
  };
}

;// ./src/content/main/snippets.entry.js
/*
 * This file is part of eyeo's Web Extension Ad Blocking Toolkit (EWE),
 * Copyright (C) 2006-present eyeo GmbH
 *
 * EWE is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License version 3 as
 * published by the Free Software Foundation.
 *
 * EWE is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with EWE.  If not, see <http://www.gnu.org/licenses/>.
 */

/* global chrome browser */








// Use chrome.storage to detect if we're in an isolated world.
// Note: chrome.runtime is unreliable since other extensions may expose it
// in the main world.
const isMainWorld = !(
  (typeof chrome === "object" && !!chrome.storage) ||
  (typeof browser === "object" && !!browser.storage)
);

const nativeDispatch = document.dispatchEvent.bind(document);

// Get or create a unique channel name for communicating with the isolated world
const commsChannelName = claimCommsChannel(esm_browser_v4());

// Creates a sendSnippetHitEvent function that dispatches hit events back to
// the isolated world via the comms channel. The isolated-world listener
// receives, validates, and forwards the event to the telemetry pipeline.
const createMainWorldHitEventSender = (commsChannel, dispatch) => {
  const dispatchFn = dispatch || document.dispatchEvent.bind(document);
  return function sendSnippetHitEvent(filter, domain) {
    try {
      dispatchFn(new CustomEvent(commsChannel, {
        detail: {
          type: "ewe:snippet-hit",
          filter,
          domain
        }
      }));
    }
    catch (e) {
      // telemetry must never break snippet execution
    }
  };
};

const runStorageShim = (shimFn, configKey) => {
  try {
    if (typeof shimFn === "function" && configKey) {
      shimFn(configKey);
    }
  }
  catch (err) {
    // It would be good to report this error to Sentry, but we don't currently
    // have a way to do that from the main world.
  }
};

const runSnippets = snippetsConfig => {
  const {callback, filters, env, commsChannel, serializeError,
    dispatchFn} = snippetsConfig;

  if (filters.length) {
    try {
      callback(env, ...filters);
    }
    catch (e) {
      // It would be good to report this error to Sentry, but we don't currently
      // have a way to do that from the main world.
      const errorEvent = new CustomEvent(commsChannel, {
        detail: {
          type: "ewe:main-error",
          error: serializeError(e)
        }
      });
      dispatchFn(errorEvent);
    }
  }
};

const createTrustedScriptPolicy = () => {
  const isTrustedTypesSupported = typeof trustedTypes !== "undefined";
  let policy = null;

  try {
    if (isTrustedTypesSupported) {
      policy = trustedTypes.createPolicy(esm_browser_v4(), {
        createScript: code => code,
        createScriptURL: url => url
      });
    }
  }
  catch (_) {
  }
  return policy;
};

const injectScript = (executable, policy) => {
  const script = document.createElement("script");
  script.type = "application/javascript";
  script.async = false;

  if (policy) {
    script.textContent = policy.createScript(executable);
  }
  else {
    script.textContent = executable;
  }

  try {
    document.documentElement.appendChild(script);
  }
  catch (_) {}
  document.documentElement.removeChild(script);
};

const appendSnippets = snippetsConfig => {
  const policy = createTrustedScriptPolicy();
  const {
    callback,
    filters,
    env,
    shimFn,
    shimConfigKey,
    commsChannel,
    serializeError
  } = snippetsConfig;

  const snippetsCode = filters.length ? `
    const callback = (${callback});
    const runSnippets = (${runSnippets});
    const serializeError = (${serializeError});
    const createHitSender = (${createMainWorldHitEventSender});
    const env = ${JSON.stringify(env)};
    env.sendSnippetHitEvent = createHitSender(
      "${commsChannel}", null
    );
    const snippetsConfig = {
      callback,
      env,
      filters: ${JSON.stringify(filters)},
      commsChannel: "${commsChannel}",
      serializeError,
      dispatchFn: document.dispatchEvent.bind(document)
    };
    runSnippets(snippetsConfig);
  ` : "";

  const code = `(function () {
    const shimFn = (${shimFn});
    const shimConfigKey = "${shimConfigKey}";
    const runStorageShim = (${runStorageShim});
    runStorageShim(shimFn, shimConfigKey);
    ${snippetsCode}
  })();`;

  injectScript(code, policy);
};

const onFiltersReceived = event => {
  if (!event || !event.detail) {
    return;
  }

  const {type, filters, debug} = event.detail;

  // ignore other events that are not related to filters config
  if (type !== "ewe:filters-config") {
    return;
  }

  // Check which snippets need to be executed in the main world.
  const mainSnippets = [];
  for (const filter of filters) {
    for (const [name, ...args] of filter) {
      if (main.has(name)) {
        mainSnippets.push([name, ...args]);
      }
    }
  }

  // sendDetectionEvent is intentionally not included in the main world env.
  // Detection events rely on ServerLogger and Sentry, which require extension
  // API access only available in the isolated world. See snippet-events.js.
  const snippetsConfig = {
    callback: main,
    env: {
      debugCSSProperties: debug ? DEBUG_CSS_PROPERTIES : null,
      sendSnippetHitEvent: createMainWorldHitEventSender(
        commsChannelName, isMainWorld ? nativeDispatch : null
      )
    },
    filters: mainSnippets,
    shimFn: shimStorage,
    shimConfigKey: CACHED_FILTERS_CONFIG_KEY,
    commsChannel: commsChannelName,
    serializeError: toSerializableError,
    dispatchFn: nativeDispatch
  };

  // If this script is injected into the main world we can execute directly.
  // If we are on isolated world (MV2), we need to create an inline script to
  // inject the snippets into page context.
  if (isMainWorld) {
    runStorageShim(shimStorage, CACHED_FILTERS_CONFIG_KEY);
    runSnippets(snippetsConfig);
  }
  else {
    appendSnippets(snippetsConfig);
  }
};

document.addEventListener(commsChannelName, onFiltersReceived);
document.dispatchEvent(new CustomEvent(HANDSHAKE_EVENT_NAME));

/******/ })()
;
