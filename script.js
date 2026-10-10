const form = document.getElementById('loginForm');
const email = document.getElementById('email');
const password = document.getElementById('password');
const emailError = document.getElementById('emailError');
const passwordError = document.getElementById('passwordError');
const status = document.getElementById('status');
const togglePassword = document.getElementById('togglePassword');
const forgotPassword = document.getElementById('forgotPassword');
const createAccount = document.getElementById('createAccount');

function clearMessages(){
  if(emailError) emailError.textContent='';
  if(passwordError) passwordError.textContent='';
  if(status) status.textContent='';
}

togglePassword?.addEventListener('click',()=>{
  const showing=password.type==='text';
  password.type=showing?'password':'text';
  togglePassword.setAttribute('aria-label',showing?'Show password':'Hide password');
});

function completeLogin(displayName, method='email') {
  localStorage.setItem('skillsync_session', JSON.stringify({
    email: method === 'email' ? email.value.trim() : `${displayName.toLowerCase().replace(/\s+/g,'')}@demo.skillsync.local`,
    displayName,
    method,
    signedInAt: new Date().toISOString()
  }));
  if(status) status.textContent='Login successful — opening your SkillSync dashboard…';
  setTimeout(()=>window.location.assign('index.html'),300);
}

form?.addEventListener('submit',(event)=>{
  event.preventDefault(); clearMessages();
  const e=email.value.trim(), p=password.value;
  let ok=true;
  if(!e){emailError.textContent='Please enter your email.';ok=false;}
  else if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e)){emailError.textContent='Please enter a valid email address.';ok=false;}
  if(!p){passwordError.textContent='Please enter your password.';ok=false;}
  else if(p.length<6){passwordError.textContent='Password must be at least 6 characters.';ok=false;}
  if(!ok)return;
  const local=e.split('@')[0].replace(/[._-]+/g,' ').replace(/\b\w/g,c=>c.toUpperCase());
  completeLogin(local || 'Student');
});

forgotPassword?.addEventListener('click',()=>{
  clearMessages();
  if(!email.value.trim()){emailError.textContent='Enter your email first and we\'ll send a reset link.';email.focus();return;}
  status.textContent=`Password reset link requested for ${email.value.trim()}.`;
});
createAccount?.addEventListener('click',()=>{clearMessages();status.textContent='Demo account creation flow — connect your real auth service here.';});
// Google Identity Services: the backend verifies the credential before creating a session.
const GOOGLE_CLIENT_ID = '113605544241-cgpch2vhnk375ap7f524j5f4rl5mdj52.apps.googleusercontent.com';
async function handleGoogleCredential(response) {
  clearMessages();
  if (status) status.textContent = 'Verifying your Google account…';
  try {
    const result = await fetch('http://127.0.0.1:8000/api/auth/google', {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({credential: response.credential})
    });
    const data = await result.json().catch(()=>({detail:'Could not read authentication response.'}));
    if (!result.ok) throw new Error(data.detail || 'Google sign-in failed.');
    localStorage.setItem('skillsync_session', JSON.stringify({
      email: data.email, displayName: data.name || data.email.split('@')[0],
      method: 'google', signedInAt: new Date().toISOString()
    }));
    if (status) status.textContent = 'Google sign-in successful — opening SkillSync…';
    window.location.assign('index.html');
  } catch (err) {
    if (status) status.textContent = err.message || 'Could not connect to SkillSync backend.';
  }
}
function initGoogleSignIn() {
  const target = document.getElementById('googleSignInButton');
  if (!target || !window.google?.accounts?.id) return false;
  target.innerHTML = '';
  google.accounts.id.initialize({client_id: GOOGLE_CLIENT_ID, callback: handleGoogleCredential});
  google.accounts.id.renderButton(target, {theme:'outline', size:'large', text:'continue_with', shape:'rectangular', width:260});
  return true;
}
let googleInitAttempts = 0;
const googleInitTimer = setInterval(() => {
  googleInitAttempts++;
  if (initGoogleSignIn() || googleInitAttempts >= 40) clearInterval(googleInitTimer);
}, 250);
// Keep non-Google social buttons clearly marked as demo-only; do not fake authentication.
document.querySelectorAll('.social:not(#googleSignInButton)').forEach(btn=>btn.addEventListener('click',()=>{
  clearMessages(); if(status) status.textContent = 'This sign-in provider is not configured yet. Please use Google or email login.';
}));
