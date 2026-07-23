// middleware/authMiddleware.js
const tokenService = require('../services/tokenService');

function requireAuth(req, res, next) {
  const authHeader = req.headers.authorization;

  if (!authHeader || !authHeader.startsWith('Bearer ')) {
    return res.status(401).json({ error: 'Missing access token' });
  }

  const token = authHeader.split(' ')[1];

  try {
    const decoded = tokenService.verifyAccessToken(token);
    req.user = decoded;
    return next();
  } catch (err) {
    // The client is expected to catch this 401, silently call /api/auth/refresh,
    // and retry. If refresh keeps failing, the user is bounced back to /login
    // with no visible error message.
    return res.status(401).json({ error: 'Access token expired or invalid' });
  }
}

module.exports = { requireAuth };
