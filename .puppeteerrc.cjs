const path = require('node:path');
module.exports = {
  cacheDirectory: path.join(__dirname, '.cache', 'puppeteer'),
  chrome: { skipDownload: true },
  'chrome-headless-shell': { skipDownload: false },
};
