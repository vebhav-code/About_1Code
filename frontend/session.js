/* =========================================================
   1Code — Shared session helper
   Reads the 1code_user session from localStorage.
   If a user is logged in, replaces the "Sign In" nav button
   with a welcome greeting + logout button.
   Include this script at the bottom of every page that has
   a nav-actions element.
   ========================================================= */

(function () {
  function getSession() {
    try {
      return JSON.parse(localStorage.getItem("1code_user") || "null");
    } catch {
      return null;
    }
  }

  function logout() {
    localStorage.removeItem("1code_user");
    window.location.href = "auth.html";
  }

  document.addEventListener("DOMContentLoaded", function () {
    const session = getSession();
    const navActions = document.querySelector(".nav-actions");
    const signInLink = navActions && navActions.querySelector('a[href="auth.html"]');

    if (!session || !navActions) return;

    // Remove or hide the Sign In link
    if (signInLink) signInLink.remove();

    // Create user pill with name + logout
    const userPill = document.createElement("div");
    userPill.className = "nav-user-pill";
    userPill.style.cssText =
      "display:flex;align-items:center;gap:10px;";

    const nameSpan = document.createElement("span");
    nameSpan.className = "nav-user-name";
    nameSpan.style.cssText =
      "font-size:.875rem;font-weight:600;color:var(--text-primary,#fff);" +
      "white-space:nowrap;max-width:140px;overflow:hidden;text-overflow:ellipsis;";
    nameSpan.textContent = session.name;

    const logoutBtn = document.createElement("button");
    logoutBtn.type = "button";
    logoutBtn.className = "btn btn-ghost";
    logoutBtn.textContent = "Log out";
    logoutBtn.style.cssText =
      "padding:6px 14px;font-size:.8rem;";
    logoutBtn.addEventListener("click", logout);

    userPill.appendChild(nameSpan);
    userPill.appendChild(logoutBtn);

    // Insert before the mobile nav toggle if it exists, else append
    const toggle = navActions.querySelector(".nav-toggle");
    if (toggle) {
      navActions.insertBefore(userPill, toggle);
    } else {
      navActions.appendChild(userPill);
    }
  });
})();
