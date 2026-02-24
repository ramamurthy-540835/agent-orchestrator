require('dotenv').config();
const express = require('express');
const path = require('path');
const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.set('view engine', 'ejs');
app.set('views', path.join(__dirname, 'views'));
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ limit: '50mb', extended: true }));
app.use(express.static(path.join(__dirname, 'public')));

// Routes
const apiRoutes = require('./routes/api');
const pageRoutes = require('./routes/pages');

app.use('/api', apiRoutes);
app.use('/', pageRoutes);

app.listen(PORT, () => {
    console.log(`Agent Orchestration Platform running at http://localhost:${PORT}`);
});
