<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>SkillSync — Login</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="styles.css" />
</head>
<body>
  <main class="page">
    <section class="hero">
      <div class="hero-overlay"></div>

      <div class="hero-copy">
        <h1>Find the right<br>opportunity before<br>it passes you by.</h1>
        <p>
          SkillSync brings hackathons, workshops,<br class="desktop-break">
          competitions and practical learning<br class="desktop-break">
          opportunities into one personalised<br class="desktop-break">
          discovery experience.
        </p>
      </div>

      <section class="login-card" aria-label="SkillSync login">
        <div class="brand">
          <div class="brand-mark" aria-hidden="true">
            <svg viewBox="0 0 64 64" fill="none">
              <path d="M31.8 6.5c7.7 5.1 15.5 9.8 22.2 16.7 2.5 2.6 2.5 7-.2 9.5l-11.1 10.2c-4.8 4.4-12.3 4.1-16.6-.7l-4.2-4.7c-3.4-3.8-3.1-9.7.7-13.1l7.8-7.1" stroke="currentColor" stroke-width="6" stroke-linecap="round"/>
              <path d="M29 19.2 18.4 8.8c-2.2-2.2-5.9-.7-5.9 2.4v11.4c0 4.9 4 8.9 8.9 8.9h10.7" stroke="currentColor" stroke-width="6" stroke-linecap="round"/>
              <path d="M34.3 10.7c.7 7.3-1.1 12.6-5.4 15.9" stroke="#76A84E" stroke-width="5" stroke-linecap="round"/>
              <path d="M40.8 9.8c-2.2 2.4-4.3 4.1-6.5 5.1" stroke="#76A84E" stroke-width="5" stroke-linecap="round"/>
            </svg>
          </div>
          <span>SkillSync</span>
        </div>

        <div class="login-content">
          <h2>Login to your account</h2>
          <p class="welcome">Welcome back! Select method to log in:</p>

          <div class="social-row">
            <button class="social google" type="button" aria-label="Continue with Google">
              <svg viewBox="0 0 24 24"><path fill="#4285F4" d="M21.35 12.23c0-.7-.06-1.37-.18-2.02H12v3.82h5.23a4.47 4.47 0 0 1-1.94 2.93v2.44h3.14c1.84-1.69 2.92-4.18 2.92-7.17z"/><path fill="#34A853" d="M12 21.75c2.63 0 4.84-.87 6.45-2.35l-3.14-2.44c-.87.58-1.98.92-3.31.92-2.55 0-4.71-1.72-5.49-4.03H3.26v2.52A9.75 9.75 0 0 0 12 21.75z"/><path fill="#FBBC05" d="M6.51 13.85a5.86 5.86 0 0 1 0-3.7V7.63H3.26a9.76 9.76 0 0 0 0 8.74l3.25-2.52z"/><path fill="#EA4335" d="M12 6.12c1.43 0 2.71.49 3.72 1.45l2.79-2.79C16.84 3.2 14.63 2.25 12 2.25a9.75 9.75 0 0 0-8.74 5.38l3.25 2.52C7.29 7.84 9.45 6.12 12 6.12z"/></svg>
            </button>
            <button class="social apple" type="button" aria-label="Continue with Apple">
              <svg viewBox="0 0 24 24"><path d="M17.05 12.7c-.02-2.18 1.78-3.23 1.86-3.28-1.02-1.49-2.6-1.7-3.15-1.72-1.33-.14-2.62.8-3.3.8-.69 0-1.75-.78-2.88-.76-1.48.02-2.84.86-3.6 2.17-1.55 2.68-.4 6.62 1.1 8.79.74 1.06 1.61 2.24 2.76 2.2 1.1-.04 1.52-.71 2.85-.71 1.33 0 1.71.71 2.86.69 1.19-.02 1.94-1.08 2.66-2.15.84-1.24 1.18-2.45 1.2-2.51-.03-.01-2.32-.89-2.36-3.52zM14.88 6.28c.6-.73 1.01-1.73.9-2.73-.87.04-1.91.58-2.53 1.3-.55.64-1.03 1.66-.9 2.63.96.08 1.94-.49 2.53-1.2z"/></svg>
            </button>
            <button class="social microsoft" type="button" aria-label="Continue with Microsoft">
              <svg viewBox="0 0 24 24"><path fill="#F35325" d="M2 2h9.5v9.5H2z"/><path fill="#81BC06" d="M12.5 2H22v9.5h-9.5z"/><path fill="#05A6F0" d="M2 12.5h9.5V22H2z"/><path fill="#FFBA08" d="M12.5 12.5H22V22h-9.5z"/></svg>
            </button>
            <button class="social facebook" type="button" aria-label="Continue with Facebook">
              <svg viewBox="0 0 24 24"><path fill="#1877F2" d="M24 12a12 12 0 1 0-13.88 11.86v-8.4H7.08V12h3.04V9.42c0-3 1.79-4.66 4.53-4.66 1.31 0 2.69.23 2.69.23v2.96h-1.51c-1.49 0-1.96.93-1.96 1.89V12h3.34l-.53 3.46h-2.81v8.4A12 12 0 0 0 24 12z"/></svg>
            </button>
          </div>

          <div class="divider"><span></span><em>Or continue with email</em><span></span></div>

          <form id="loginForm" novalidate>
            <label for="email">Email</label>
            <div class="field">
              <svg class="field-icon" viewBox="0 0 24 24" fill="none"><rect x="3" y="5" width="18" height="14" rx="2" stroke="currentColor" stroke-width="1.8"/><path d="m4 7 8 6 8-6" stroke="currentColor" stroke-width="1.8"/></svg>
              <input id="email" type="email" placeholder="janetannmyers@gmail.com" autocomplete="email" />
            </div>
            <div class="error" id="emailError"></div>

            <label for="password">Password</label>
            <div class="field">
              <svg class="field-icon" viewBox="0 0 24 24" fill="none"><rect x="5" y="10" width="14" height="10" rx="2" stroke="currentColor" stroke-width="1.8"/><path d="M8 10V7a4 4 0 0 1 8 0v3" stroke="currentColor" stroke-width="1.8"/><circle cx="12" cy="15" r="1.2" fill="currentColor"/></svg>
              <input id="password" type="password" placeholder="••••••••••" autocomplete="current-password" />
              <button type="button" class="eye" id="togglePassword" aria-label="Show password">
                <svg viewBox="0 0 24 24" fill="none"><path d="M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z" stroke="currentColor" stroke-width="1.7"/><circle cx="12" cy="12" r="2.5" stroke="currentColor" stroke-width="1.7"/><path d="m4 4 16 16" stroke="currentColor" stroke-width="1.7"/></svg>
              </button>
            </div>
            <div class="error" id="passwordError"></div>

            <div class="options">
              <label class="remember">
                <input type="checkbox" id="remember" checked />
                <span class="checkmark">✓</span>
                <span>Remember me</span>
              </label>
              <button type="button" class="link-button" id="forgotPassword">Forgot password?</button>
            </div>

            <button class="login-button" type="submit">Login</button>
            <div class="status" id="status"></div>
          </form>

          <p class="create-account">
            Don't have an account?
            <button type="button" class="link-button" id="createAccount">Create an account</button>
          </p>
        </div>

      </section>
    </section>
  </main>

  <script src="script.js"></script>
</body>
</html>