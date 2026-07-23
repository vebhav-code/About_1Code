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
  return jwt.verify(token, config.JWT_SECRET);
}

module.exports = {
  signAccessToken,
  signRefreshToken,
  verifyAccessToken,
  verifyRefreshToken
};
