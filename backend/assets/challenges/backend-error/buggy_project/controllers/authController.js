// controllers/authController.js
const tokenService = require('../services/tokenService');

// Fake single-user "database" so the challenge has zero external
// dependencies (no real DB needed to reproduce the bug).
const FAKE_USER = { id: 1, username: 'demo', password: 'demo123' };

function login(req, res) {
  const { username, password } = req.body || {};

  if (username !== FAKE_USER.username || password !== FAKE_USER.password) {
    return res.status(401).json({ error: 'Invalid credentials' });
  }

  const payload = { sub: FAKE_USER.id, username: FAKE_USER.username };

  const accessToken = tokenService.signAccessToken(payload);
  const refreshToken = tokenService.signRefreshToken(payload);

  // Refresh token lives in an httpOnly cookie so client-side JS can't read it.
  res.cookie('refreshToken', refreshToken, {
    httpOnly: true,
    maxAge: 7 * 24 * 60 * 60 * 1000
  });

  return res.json({ accessToken });
}

function refresh(req, res) {
  const refreshToken = req.cookies ? req.cookies.refreshToken : undefined;

  if (!refreshToken) {
    return res.status(401).json({ error: 'No refresh token provided' });
  }

  try {
    const decoded = tokenService.verifyRefreshToken(refreshToken);
    const payload = { sub: decoded.sub, username: decoded.username };
    const newAccessToken = tokenService.signAccessToken(payload);
    return res.json({ accessToken: newAccessToken });
  } catch (err) {
    return res.status(401).json({ error: 'Invalid or expired refresh token' });
  }
}

function logout(req, res) {
  res.clearCookie('refreshToken');
  return res.json({ message: 'Logged out' });
}

function me(req, res) {
  return res.json({ user: req.user });
}

module.exports = { login, refresh, logout, me };
