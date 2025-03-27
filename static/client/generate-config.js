// generate-config.js
require('dotenv').config();
const fs = require('fs');

const config = {
    ARI_WS_URL: process.env.ARI_WS_URL || 'ws://localhost:8088/ari/events',
    ASTERISK_HOST: process.env.ASTERISK_HOST || 'localhost',
    // Add any other env vars needed
};

fs.writeFileSync(
    './public/config.js',
    `window.CONFIG = ${JSON.stringify(config, null, 2)};`
);