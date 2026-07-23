// services/tokenService.js
// Wraps all JWT signing/verification logic in one place so the rest
// of the app never touches the `jsonwebtoken` library directly.

const jwt = require('jsonwebtoken');
const config = require('../config');

function signAccessToken(payload) {
  return jwt.sign(payload, config.JWT_SECRET, {
    expiresIn: config.ACCESS_TOKEN_TTL
  });
}

function signRefreshToken(payload) {
  return jwt.sign(payload, config.JWT_REFRESH_SECRET, {
    expiresIn: config.REFRESH_TOKEN_TTL
  });
}

function verifyAccessToken(token) {
  return jwt.verify(token, config.JWT_SECRET);
}

function verifyRefreshToken(token) {
  // FIX: refresh tokens were signed with JWT_REFRESH_SECRET, so they must
  // also be verified with JWT_REFRESH_SECRET. The buggy version verified
  // them with JWT_SECRET (the access-token secret), which made every
  // refresh attempt throw a JsonWebTokenError ("invalid signature"). The
  // /api/auth/refresh handler caught that error and returned 401, so once
  // the short-lived access token expired the user was silently logged out
  // even though their refresh token was perfectly valid.
  return jwt.verify(token, config.JWT_REFRESH_SECRET);
}

module.exports = {
  signAccessToken,
  signRefreshToken,
  verifyAccessToken,
  verifyRefreshToken
};
