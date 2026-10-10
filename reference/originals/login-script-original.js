const form = document.getElementById("loginForm");
const email = document.getElementById("email");
const password = document.getElementById("password");
const emailError = document.getElementById("emailError");
const passwordError = document.getElementById("passwordError");
const status = document.getElementById("status");
const togglePassword = document.getElementById("togglePassword");
const forgotPassword = document.getElementById("forgotPassword");
const createAccount = document.getElementById("createAccount");

function clearMessages() {
  emailError.textContent = "";
  passwordError.textContent = "";
  status.textContent = "";
}

togglePassword.addEventListener("click", () => {
  const showing = password.type === "text";
  password.type = showing ? "password" : "text";
  togglePassword.setAttribute("aria-label", showing ? "Show password" : "Hide password");

  togglePassword.innerHTML = showing
    ? `<svg viewBox="0 0 24 24" fill="none">
         <path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z" stroke="currentColor" stroke-width="1.7"/>
         <circle cx="12" cy="12" r="2.5" stroke="currentColor" stroke-width="1.7"/>
         <path d="m4 4 16 16" stroke="currentColor" stroke-width="1.7"/>
       </svg>`
    : `<svg viewBox="0 0 24 24" fill="none">
         <path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z" stroke="currentColor" stroke-width="1.7"/>
         <circle cx="12" cy="12" r="2.5" stroke="currentColor" stroke-width="1.7"/>
       </svg>`;
});

form.addEventListener("submit", (event) => {
  event.preventDefault();
  clearMessages();

  const emailValue = email.value.trim();
  const passwordValue = password.value;

  let valid = true;

  if (!emailValue) {
    emailError.textContent = "Please enter your email.";
    valid = false;
  } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailValue)) {
    emailError.textContent = "Please enter a valid email address.";
    valid = false;
  }

  if (!passwordValue) {
    passwordError.textContent = "Please enter your password.";
    valid = false;
  } else if (passwordValue.length < 6) {
    passwordError.textContent = "Password must be at least 6 characters.";
    valid = false;
  }

  if (!valid) return;

  status.textContent = "Login successful — connecting to SkillSync…";

  // Replace this demo behavior with your real authentication/API call.
  setTimeout(() => {
    status.textContent = "Welcome back to SkillSync!";
  }, 900);
});

forgotPassword.addEventListener("click", () => {
  clearMessages();

  const emailValue = email.value.trim();

  if (!emailValue) {
    emailError.textContent = "Enter your email first and we'll send a reset link.";
    email.focus();
    return;
  }

  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(emailValue)) {
    emailError.textContent = "Please enter a valid email address.";
    email.focus();
    return;
  }

  status.textContent = `Password reset link requested for ${emailValue}.`;
});

createAccount.addEventListener("click", () => {
  clearMessages();
  status.textContent = "Account creation flow can be connected here.";
});

document.querySelectorAll(".social").forEach((button) => {
  button.addEventListener("click", () => {
    clearMessages();
    const provider = button.getAttribute("aria-label").replace("Continue with ", "");
    status.textContent = `${provider} sign-in selected.`;
  });
});