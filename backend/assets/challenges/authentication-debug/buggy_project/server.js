// server.js
const express = require('express');
const cookieParser = require('cookie-parser');

const config = require('./config');
const routes = require('./routes');

const app = express();

app.use(express.json());
app.use(cookieParser());
app.use('/api/auth', routes);

app.get('/health', (req, res) => {
  res.json({ status: 'ok' });
});

if (require.main === module) {
  app.listen(config.PORT, () => {
    console.log(`Server running on port ${config.PORT}`);
  });
}

module.exports = app;
