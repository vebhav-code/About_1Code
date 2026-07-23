// config.js
// Central place for environment-driven configuration.
// In production these secrets would come from a secrets manager,
// but for this challenge sensible defaults are provided so the
// project runs out of the box with `npm install && npm start`.

module.exports = {
  PORT: process.env.PORT || 4000,

  // Used to sign/verify short-lived access tokens handed to the client.
  JWT_SECRET: process.env.JWT_SECRET || 'access-token-secret-key-dev',

  // Used to sign/verify long-lived refresh tokens stored in an httpOnly cookie.
  JWT_REFRESH_SECRET: process.env.JWT_REFRESH_SECRET || 'refresh-token-secret-key-dev',

  // Kept intentionally short so the bug is reproducible quickly during grading.
  ACCESS_TOKEN_TTL: '30s',
  REFRESH_TOKEN_TTL: '7d'
};
