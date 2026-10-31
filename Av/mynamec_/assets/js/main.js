// Aishwarya Arts & Sports Club — main.js

// Navbar scroll
const nav=document.getElementById('mainNav');
if(nav)window.addEventListener('scroll',()=>nav.classList.toggle('scrolled',scrollY>30));

// Hamburger
const ham=document.getElementById('hamburger'),nl=document.getElementById('navLinks');
if(ham&&nl){
  ham.addEventListener('click',()=>nl.classList.toggle('open'));
  document.addEventListener('click',e=>{if(!ham.contains(e.target)&&!nl.contains(e.target))nl.classList.remove('open');});
}

// OTP digits
const digits=[...document.querySelectorAll('.otp-digit')];
digits.forEach((d,i)=>{
  d.addEventListener('input',e=>{e.target.value=e.target.value.replace(/\D/g,'').slice(-1);if(e.target.value&&i<digits.length-1)digits[i+1].focus();});
  d.addEventListener('keydown',e=>{if(e.key==='Backspace'&&!d.value&&i>0)digits[i-1].focus();});
});

// OTP form
const otpForm=document.getElementById('otpForm');
if(otpForm){
  otpForm.addEventListener('submit',e=>{
    const otp=digits.map(d=>d.value).join('');
    const h=document.getElementById('otpHidden');if(h)h.value=otp;
    if(otp.length<6){e.preventDefault();alert('Please enter the full 6-digit OTP.');}
  });
}

// Auto-dismiss alerts
document.querySelectorAll('.alert').forEach(a=>{setTimeout(()=>{a.style.opacity='0';setTimeout(()=>a.remove(),400);},6000);});

// Confirm buttons
document.querySelectorAll('[data-confirm]').forEach(b=>b.addEventListener('click',e=>{if(!confirm(b.dataset.confirm))e.preventDefault();}));

// Subscription expiry colours
document.querySelectorAll('[data-expiry]').forEach(el=>{
  const d=new Date(el.dataset.expiry),now=new Date();
  const diff=Math.ceil((d-now)/86400000);
  if(diff<0)el.style.color='var(--red)';
  else if(diff<=7)el.style.color='#E65100';
  else el.style.color='var(--green)';
});
