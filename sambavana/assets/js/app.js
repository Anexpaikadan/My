if('serviceWorker' in navigator)navigator.serviceWorker.register('sw.js').catch(function(){});
var dp=null,b=document.getElementById('inst');
window.addEventListener('beforeinstallprompt',function(e){e.preventDefault();dp=e;if(b)b.classList.remove('d-none');});
if(b)b.onclick=function(){if(dp){dp.prompt();dp.userChoice.then(function(){dp=null;b.classList.add('d-none');});}};
window.addEventListener('appinstalled',function(){if(b)b.classList.add('d-none');});
var ios=/iphone|ipad|ipod/i.test(navigator.userAgent),sa=navigator.standalone||matchMedia('(display-mode: standalone)').matches,seen=false;
try{seen=localStorage.getItem('iosHint');}catch(x){}
if(ios&&!sa&&!seen){var d=document.createElement('div');d.className='alert alert-info small noprint';
d.innerHTML='\ud83d\udcf2 Install: tap <b>Share</b> \u2192 <b>Add to Home Screen</b> <button type="button" class="btn-close float-end"></button>';
d.querySelector('button').onclick=function(){d.remove();try{localStorage.setItem('iosHint','1');}catch(x){}};
var c=document.querySelector('.container.py-3');if(c)c.prepend(d);}
// App feel: tapping a link or sending a form shows a loading bar at once and fades the page
function go(){document.body.classList.add('go');clearTimeout(window.goT);window.goT=setTimeout(function(){document.body.classList.remove('go');},8000);}
document.addEventListener('click',function(e){var a=e.target.closest('a[href]');
 if(!a||e.defaultPrevented||a.target||a.hasAttribute('download')||e.ctrlKey||e.metaKey||e.shiftKey)return;
 if(a.origin!==location.origin||a.getAttribute('href').charAt(0)==='#')return;
 if(a.pathname===location.pathname&&a.search===location.search&&a.hash)return;
 go();});
// Saving: no internet = don't send (nothing is lost, try again). Otherwise lock the buttons so a
// second tap cannot send it twice (the server also ignores a repeated form, see csrf_check).
function toast(m){var t=document.getElementById('toast');if(!t){t=document.createElement('div');t.id='toast';document.body.appendChild(t);}
 t.textContent=m;t.className='show';clearTimeout(window.toastT);window.toastT=setTimeout(function(){t.className='';},3500);}
document.addEventListener('submit',function(e){var f=e.target;if(e.defaultPrevented||f.target)return;
 if((f.method||'').toLowerCase()==='post'){
  if(!navigator.onLine){e.preventDefault();toast('📶 No internet — not saved. Try again when online. / ഇന്റർനെറ്റ് ഇല്ല');return;}
  if(f.dataset.sending){e.preventDefault();return;}
  f.dataset.sending='1';
  var b=e.submitter;
  if(b&&b.name){var h=document.createElement('input');h.type='hidden';h.name=b.name;h.value=b.value;h.className='subh';f.appendChild(h);}
  f.querySelectorAll('button,[type=submit]').forEach(function(x){x.disabled=true;});
  if(b){b.dataset.t=b.innerHTML;b.innerHTML='<span class="spinner-border spinner-border-sm"></span> Saving…';}
 }
 go();});
window.addEventListener('pageshow',function(){document.body.classList.remove('go');
 document.querySelectorAll('form[data-sending]').forEach(function(f){delete f.dataset.sending;f.querySelectorAll('.subh').forEach(function(h){h.remove();});
  f.querySelectorAll('button,[type=submit]').forEach(function(x){x.disabled=false;if(x.dataset.t){x.innerHTML=x.dataset.t;delete x.dataset.t;}});});});
window.addEventListener('offline',function(){toast('📶 You are offline / ഓഫ്‌ലൈൻ');});
