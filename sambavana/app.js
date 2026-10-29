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
