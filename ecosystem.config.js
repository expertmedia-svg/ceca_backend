const path = require('node:path');

module.exports = {
  apps: [{
    name: 'ceca-backend',
    cwd: __dirname,
    script: path.join(__dirname, '.venv', 'bin', 'python'),
    interpreter: 'none',
    args: ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8657', '--proxy-headers', '--forwarded-allow-ips', '127.0.0.1'],
    exec_mode: 'fork',
    instances: 1,
    watch: false,
    autorestart: true,
    restart_delay: 3000,
    kill_timeout: 15000,
    time: true,
    env: {
      PYTHONUNBUFFERED: '1',
      PYTHONDONTWRITEBYTECODE: '1',
      ENVIRONMENT: 'production',
      COOKIE_SECURE: 'true',
      COOKIE_SAMESITE: 'none',
      SEED_WORK_DATA: 'false',
    },
  }],
};
