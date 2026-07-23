// routes.js
const express = require('express');
const router = express.Router();

const authController = require('./controllers/authController');
const { requireAuth } = require('./middleware/authMiddleware');

router.post('/login', authController.login);
router.post('/refresh', authController.refresh);
router.post('/logout', authController.logout);
router.get('/me', requireAuth, authController.me);

module.exports = router;
