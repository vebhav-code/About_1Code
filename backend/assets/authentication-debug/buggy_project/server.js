// Buggy Express.js auth server — AUTH-001
// Bug: Session expires after ~40 seconds instead of 24 hours

const express = require('express');
const jwt = require('jsonwebtoken');
const app = express();

app.use(express.json());

const SECRET = 'super-secret-key';
const users = [
  { id: 1, email: 'admin@example.com', password: 'password123' }
];

// BUG IS HERE: expiresIn is set to 40 (seconds) instead of '24h'
// The developer likely meant 24 hours but wrote 40 by mistake
app.post('/login', (req, res) => {
  const { email, password } = req.body;
  const user = users.find(u => u.email === email && u.password === password);

  if (!user) {
    return res.status(401).json({ error: 'Invalid credentials' });
  }

  const token = jwt.sign(
    { userId: user.id, email: user.email },
    SECRET,
    { expiresIn: 40 }  // BUG: 40 seconds, not '24h'
  );

  res.json({ token, user: { id: user.id, email: user.email } });
});

app.get('/profile', (req, res) => {
  const authHeader = req.headers.authorization;
  if (!authHeader) return res.status(401).json({ error: 'No token' });

  try {
    const token = authHeader.split(' ')[1];
    const decoded = jwt.verify(token, SECRET);
    res.json({ user: decoded });
  } catch (err) {
    res.status(401).json({ error: 'Token expired or invalid' });
  }
});

app.listen(3000, () => console.log('Server running on :3000'));
