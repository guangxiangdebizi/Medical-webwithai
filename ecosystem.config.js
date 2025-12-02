/**
 * PM2 Ecosystem Configuration
 * Dolphin Trinity AI™
 * 
 * Usage:
 *   pm2 start ecosystem.config.js
 *   pm2 start ecosystem.config.js --only trinity-backend
 *   pm2 start ecosystem.config.js --only trinity-frontend
 */

module.exports = {
  apps: [
    {
      name: 'trinity-backend',
      cwd: '/home/ec2-user/AIWebHere/Medical-webwithai/backend1',
      script: '/home/ec2-user/AIWebHere/Medical-webwithai/.venv1/bin/python',
      args: 'server.py',
      interpreter: 'none',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '500M',
      env: {
        PORT: 8081,
        PYTHONUNBUFFERED: '1'
      },
      error_file: '/home/ec2-user/AIWebHere/Medical-webwithai/logs/trinity-backend-error.log',
      out_file: '/home/ec2-user/AIWebHere/Medical-webwithai/logs/trinity-backend-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    },
    {
      name: 'trinity-frontend',
      cwd: '/home/ec2-user/AIWebHere/Medical-webwithai/frontend1',
      script: '/home/ec2-user/AIWebHere/Medical-webwithai/.venv1/bin/python',
      args: 'server.py',
      interpreter: 'none',
      instances: 1,
      autorestart: true,
      watch: false,
      max_memory_restart: '200M',
      env: {
        PORT: 3031,
        PYTHONUNBUFFERED: '1'
      },
      error_file: '/home/ec2-user/AIWebHere/Medical-webwithai/logs/trinity-frontend-error.log',
      out_file: '/home/ec2-user/AIWebHere/Medical-webwithai/logs/trinity-frontend-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss Z'
    }
  ]
};


