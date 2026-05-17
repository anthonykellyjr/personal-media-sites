const express = require('express');
const nodemailer = require('nodemailer');
const fetch = require('node-fetch');
const fs = require('fs').promises;
const path = require('path');
require('dotenv').config();

const app = express();
const port = process.env.PORT || 3001;

// Middleware
app.use(express.json());
app.use(express.urlencoded({ extended: true }));
app.use('/docker-services', express.static(path.join(__dirname, '../docker-services')));

// Enhanced CORS configuration
app.use((req, res, next) => {
    const origin = req.headers.origin;
    const exactOrigins = process.env.ALLOWED_ORIGINS?.split(',') || [];
    let isAllowed = exactOrigins.includes(origin);
    
    if (!isAllowed && process.env.ALLOWED_ORIGIN_PATTERNS) {
        const patterns = process.env.ALLOWED_ORIGIN_PATTERNS.split(',');
        isAllowed = patterns.some(pattern => {
            if (pattern.includes('*')) {
                const regex = new RegExp('^' + pattern
                    .replace(/\./g, '\\.')
                    .replace(/\*/g, '.*') + '$');
                return regex.test(origin);
            }
            return pattern === origin;
        });
    }
    
    if (isAllowed || !origin) {
        res.header('Access-Control-Allow-Origin', origin || '*');
    }
    
    res.header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS');
    res.header('Access-Control-Allow-Headers', 'Content-Type, Authorization, X-Api-Key');
    
    if (req.method === 'OPTIONS') {
        return res.sendStatus(200);
    }
    
    next();
});

// Request logging middleware
app.use((req, res, next) => {
    console.log(`${new Date().toISOString()} - ${req.method} ${req.path} - ${req.ip}`);
    next();
});

// Initialize email transporter if credentials are provided
let emailTransporter = null;
if (process.env.EMAIL_USER && process.env.EMAIL_PASS) {
    emailTransporter = nodemailer.createTransport({
        service: 'gmail',
        auth: {
            user: process.env.EMAIL_USER,
            pass: process.env.EMAIL_PASS
        }
    });
    console.log('Email service initialized');
}

// ============= UTILITY FUNCTIONS =============

async function sendNtfyNotification(topic, title, message, options = {}) {
    const ntfyUrl = process.env.NTFY_URL || 'https://ntfy.webheadmedia.com';
    
    try {
        const response = await fetch(`${ntfyUrl}/${topic}`, {
            method: 'POST',
            headers: {
                'Title': title,
                'Priority': options.priority || '3',
                'Tags': options.tags || 'notification',
                ...(process.env.NTFY_AUTH && { 'Authorization': `Bearer ${process.env.NTFY_AUTH}` })
            },
            body: message
        });
        
        if (!response.ok) {
            throw new Error(`ntfy responded with ${response.status}`);
        }
        
        return { success: true };
    } catch (error) {
        console.error('ntfy error:', error);
        return { success: false, error: error.message };
    }
}

async function sendEmail(to, subject, htmlContent, textContent) {
    if (!emailTransporter) {
        console.warn('Email service not configured');
        return { success: false, error: 'Email service not configured' };
    }
    
    try {
        await emailTransporter.sendMail({
            from: process.env.EMAIL_USER,
            to: to,
            subject: subject,
            html: htmlContent,
            text: textContent
        });
        return { success: true };
    } catch (error) {
        console.error('Email error:', error);
        return { success: false, error: error.message };
    }
}

async function logToCSV(filename, data) {
    try {
        const logDir = path.join(__dirname, 'logs');
        await fs.mkdir(logDir, { recursive: true });
        
        const filepath = path.join(logDir, filename);
        const csvLine = Object.values(data).map(v => `"${v}"`).join(',') + '\n';
        
        await fs.appendFile(filepath, csvLine);
        return { success: true };
    } catch (error) {
        console.error('CSV logging error:', error);
        return { success: false, error: error.message };
    }
}

// ============= NEW: OVERSEERR PROXY =============

// Proxy all Overseerr API requests
app.all('/api/overseerr/*', async (req, res) => {
    const overseerrPath = req.path.replace('/api/overseerr/', '');
    const queryString = req.url.includes('?') ? req.url.substring(req.url.indexOf('?')) : '';
    const overseerrUrl = `http://overseerr:5055/api/${overseerrPath}${queryString}`;
    
    console.log(`Proxying to Overseerr: ${req.method} ${overseerrUrl}`);
    
    try {
        const headers = {
            'X-Api-Key': req.headers['x-api-key'],
            'Content-Type': 'application/json'
        };
        
        const options = {
            method: req.method,
            headers: headers
        };
        
        if (req.method !== 'GET' && req.method !== 'HEAD') {
            options.body = JSON.stringify(req.body);
        }
        
        const response = await fetch(overseerrUrl, options);
        const data = await response.json();
        
        res.status(response.status).json(data);
    } catch (error) {
        console.error('Overseerr proxy error:', error);
        res.status(500).json({ error: 'Proxy request failed', details: error.message });
    }
});

// Simplified ntfy notification endpoint
app.post('/api/ntfy', async (req, res) => {
    const message = typeof req.body === 'string' ? req.body : req.body.message || JSON.stringify(req.body);
    const topic = req.body.topic || 'requests';
    const title = req.body.title || 'Media Request';
    
    const result = await sendNtfyNotification(topic, title, message);
    res.json(result);
});

// ============= API ENDPOINTS =============

app.get('/api/health', (req, res) => {
    res.json({ 
        status: 'ok', 
        timestamp: new Date().toISOString(),
        services: {
            email: !!emailTransporter,
            ntfy: !!process.env.NTFY_URL || true,
            overseerr: 'http://overseerr:5055'
        },
        version: '2.0.0'
    });
});

app.get('/', (req, res) => {
    res.json({
        message: 'WebHead Media API Server',
        endpoints: [
            'GET /api/health',
            'ALL /api/overseerr/* (Overseerr proxy)',
            'POST /api/ntfy (Send notification)',
            'POST /api/join-request',
            'POST /api/media-request',
            'POST /api/contact',
            'POST /api/webhook/:service',
            'GET /api/status/:service',
            'GET /api/backup-status',
            'GET /api/backup-details',
            'GET /api/docker-stats',
            'GET /api/docker-services',
            'POST /api/docker-services'
        ]
    });
});

app.post('/api/join-request', async (req, res) => {
    const { name, email } = req.body;
    
    if (!name || !email) {
        return res.status(400).json({ error: 'Name and email are required' });
    }
    
    const timestamp = new Date().toISOString();
    const results = {};
    
    results.ntfy = await sendNtfyNotification(
        'plex-requests',
        'New Plex Join Request',
        `Name: ${name}\nEmail: ${email}\nTime: ${new Date().toLocaleString()}`,
        { tags: 'movie_camera,new_user' }
    );
    
    const emailHtml = `
        <h2>New Plex Join Request</h2>
        <p><strong>Name:</strong> ${name}</p>
        <p><strong>Email:</strong> ${email}</p>
        <p><strong>Time:</strong> ${new Date().toLocaleString()}</p>
    `;
    
    results.email = await sendEmail(
        process.env.ADMIN_EMAIL || 'anthony.d.kelly@gmail.com',
        `New Plex Join Request - ${name}`,
        emailHtml,
        `New Plex Join Request\n\nName: ${name}\nEmail: ${email}`
    );
    
    results.log = await logToCSV('plex-requests.csv', {
        timestamp,
        name,
        email
    });
    
    if (results.ntfy.success || results.email.success) {
        res.json({ 
            success: true, 
            message: 'Request processed successfully',
            results 
        });
    } else {
        res.status(500).json({ 
            error: 'Failed to process request',
            results 
        });
    }
});

app.post('/api/media-request', async (req, res) => {
    const { type, title, user, tmdbId } = req.body;
    
    if (!type || !title) {
        return res.status(400).json({ error: 'Type and title are required' });
    }
    
    const results = {};
    
    results.ntfy = await sendNtfyNotification(
        'media-requests',
        `New ${type} Request`,
        `User: ${user || 'Anonymous'}\nTitle: ${title}\nTMDB ID: ${tmdbId || 'N/A'}`,
        { tags: type === 'movie' ? 'film' : 'tv' }
    );
    
    res.json({ success: results.ntfy.success, results });
});

app.post('/api/contact', async (req, res) => {
    const { name, email, subject, message } = req.body;
    
    if (!email || !message) {
        return res.status(400).json({ error: 'Email and message are required' });
    }
    
    const results = {};
    
    results.ntfy = await sendNtfyNotification(
        'contact-form',
        subject || 'New Contact Form Submission',
        `From: ${name || 'Anonymous'} <${email}>\n\n${message}`,
        { tags: 'email,contact' }
    );
    
    if (emailTransporter) {
        const emailHtml = `
            <h2>Contact Form Submission</h2>
            <p><strong>From:</strong> ${name || 'Anonymous'} &lt;${email}&gt;</p>
            <p><strong>Subject:</strong> ${subject || 'No subject'}</p>
            <hr>
            <p>${message.replace(/\n/g, '<br>')}</p>
        `;
        
        results.email = await sendEmail(
            process.env.ADMIN_EMAIL || 'anthony.d.kelly@gmail.com',
            `Contact Form: ${subject || 'New Message'}`,
            emailHtml,
            `From: ${name} <${email}>\nSubject: ${subject}\n\n${message}`
        );
    }
    
    res.json({ 
        success: results.ntfy.success || results.email?.success || false,
        results 
    });
});

app.get('/api/docker-stats', async (req, res) => {
    try {
        const statsData = await fs.readFile('/app/docker-stats.json', 'utf8');
        if (!statsData.trim()) {
            return res.status(503).json({ error: 'Stats file is empty. Waiting for data...' });
        }
        
        const lines = statsData.trim().split('\n').filter(line => line);
        const containers = lines.map(line => {
            const data = JSON.parse(line);
            return {
                name: data.Name,
                cpu: data.CPUPerc,
                memory: data.MemUsage,
                memoryPerc: data.MemPerc,
                netIO: data.NetIO,
                blockIO: data.BlockIO,
                pids: data.PIDs,
                status: data.CPUPerc !== "0.00%" ? 'running' : 'idle'
            };
        });
        
        res.json({
            containers: containers,
            summary: {
                total: containers.length,
                running: containers.filter(c => c.status === 'running').length,
                idle: containers.filter(c => c.status === 'idle').length
            }
        });
    } catch (error) {
        console.error('Error reading docker stats:', error);
        res.status(500).json({ error: error.message });
    }
});

app.get('/api/test', (req, res) => {
    res.json({ status: 'ok', message: 'API is working' });
});

app.post('/api/webhook/:service', async (req, res) => {
    const { service } = req.params;
    const payload = req.body;
    
    console.log(`Webhook received for ${service}:`, JSON.stringify(payload, null, 2));
    
    await sendNtfyNotification(
        `webhook-${service}`,
        `Webhook: ${service}`,
        JSON.stringify(payload, null, 2),
        { tags: 'webhook,automated' }
    );
    
    await logToCSV(`webhooks-${service}.csv`, {
        timestamp: new Date().toISOString(),
        service,
        payload: JSON.stringify(payload)
    });
    
    res.json({ success: true, message: 'Webhook processed' });
});

app.get('/api/status/:service', async (req, res) => {
    const { service } = req.params;
    
    const services = {
        plex: 'https://plex.webheadmedia.com',
        overseerr: 'https://overseerr.webheadmedia.com',
        tautulli: 'https://tautulli.webheadmedia.com',
        ntfy: process.env.NTFY_URL || 'https://ntfy.webheadmedia.com'
    };
    
    if (!services[service]) {
        return res.status(404).json({ error: 'Service not found' });
    }
    
    try {
        const response = await fetch(services[service], { 
            timeout: 5000,
            headers: { 'User-Agent': 'WebHead-Monitor/1.0' }
        });
        
        res.json({
            service,
            status: response.ok ? 'online' : 'error',
            statusCode: response.status,
            timestamp: new Date().toISOString()
        });
    } catch (error) {
        res.json({
            service,
            status: 'offline',
            error: error.message,
            timestamp: new Date().toISOString()
        });
    }
});

app.get('/api/backup-status', async (req, res) => {
    const { execSync } = require('child_process');
    
    try {
        const backupMarker = '/mnt/backup_pool/last_successful_backup';
        
        try {
            await fs.access(backupMarker);
        } catch (error) {
            return res.json({
                status: 'error',
                message: 'No backup found',
                color: 'red',
                lastBackup: null,
                details: 'Backup system not initialized'
            });
        }
        
        const stats = await fs.stat(backupMarker);
        const lastBackupTime = stats.mtime;
        const now = new Date();
        const hoursAgo = (now - lastBackupTime) / (1000 * 60 * 60);
        
        let isRunning = false;
        try {
            execSync('pgrep -f tower-backup.sh', { encoding: 'utf8' });
            isRunning = true;
        } catch (e) {}
        
        let backupSizes = {};
        try {
            const sources = ['storage', 'docker_apps', 'system'];
            for (const source of sources) {
                const sourcePath = `/mnt/backup_pool/${source}`;
                try {
                    await fs.access(sourcePath);
                    const size = execSync(`du -sh ${sourcePath} | awk '{print $1}'`, { encoding: 'utf8' }).trim();
                    backupSizes[source] = size;
                } catch (e) {}
            }
        } catch (e) {
            console.error('Error getting backup sizes:', e);
        }
        
        let availableSpace = 'Unknown';
        try {
            availableSpace = execSync("df -h /mnt/backup_pool | awk 'NR==2 {print $4}'", { encoding: 'utf8' }).trim();
        } catch (e) {
            console.error('Error getting available space:', e);
        }
        
        let status, color, message;
        
        if (isRunning) {
            status = 'running';
            color = 'blue';
            message = 'Backup in progress...';
        } else if (hoursAgo > 26) {
            status = 'warning';
            color = 'yellow';
            message = `Last backup: ${hoursAgo.toFixed(1)} hours ago`;
        } else {
            status = 'success';
            color = 'green';
            message = `Last backup: ${hoursAgo.toFixed(1)} hours ago`;
        }
        
        res.json({
            status: status,
            message: message,
            color: color,
            lastBackup: lastBackupTime,
            hoursAgo: hoursAgo.toFixed(1),
            isRunning: isRunning,
            sizes: backupSizes,
            availableSpace: availableSpace,
            details: {
                storage: backupSizes.storage || 'N/A',
                docker: backupSizes.docker_apps || 'N/A',
                system: backupSizes.system || 'N/A',
                free: availableSpace
            }
        });
        
    } catch (error) {
        console.error('Error in backup-status endpoint:', error);
        res.status(500).json({
            status: 'error',
            message: 'Failed to check backup status',
            color: 'red',
            error: error.message
        });
    }
});

app.get('/api/backup-details', async (req, res) => {
    const { execSync } = require('child_process');
    
    try {
        const logDir = '/var/log/tower-backup';
        
        let latestLog = null;
        try {
            const files = await fs.readdir(logDir);
            const logFiles = files
                .filter(f => f.startsWith('backup-') && f.endsWith('.log'))
                .map(f => ({ name: f, path: path.join(logDir, f) }));
            
            const filesWithStats = await Promise.all(
                logFiles.map(async (file) => ({
                    ...file,
                    mtime: (await fs.stat(file.path)).mtime
                }))
            );
            
            filesWithStats.sort((a, b) => b.mtime - a.mtime);
            
            if (filesWithStats.length > 0) {
                latestLog = filesWithStats[0].name;
            }
        } catch (e) {
            console.error('Error reading log directory:', e);
        }
        
        let logTail = [];
        if (latestLog) {
            try {
                const logContent = execSync(`tail -20 ${path.join(logDir, latestLog)}`, { encoding: 'utf8' });
                logTail = logContent.split('\n').filter(line => line.trim());
            } catch (e) {
                console.error('Error reading log file:', e);
            }
        }
        
        res.json({
            latestLog: latestLog,
            logTail: logTail,
            logDir: logDir
        });
        
    } catch (error) {
        res.status(500).json({
            error: error.message
        });
    }
});

const DOCKER_DATA_FILE = path.join(__dirname, 'docker-services-data.json');

app.get('/api/docker-services', async (req, res) => {
    try {
        const data = await fs.readFile(DOCKER_DATA_FILE, 'utf8');
        res.json(JSON.parse(data));
    } catch (error) {
        if (error.code === 'ENOENT') {
            res.json({ tower: {}, mac: {} });
        } else {
            console.error('Error reading docker services data:', error);
            res.status(500).json({ error: 'Failed to read data' });
        }
    }
});

app.post('/api/docker-services', async (req, res) => {
    try {
        const data = req.body;
        await fs.writeFile(DOCKER_DATA_FILE, JSON.stringify(data, null, 2));
        res.json({ message: 'Data saved successfully' });
    } catch (error) {
        console.error('Error saving docker services data:', error);
        res.status(500).json({ error: 'Failed to save data' });
    }
});

// Add this endpoint after your existing endpoints
app.post('/api/issue-report', async (req, res) => {
    const { title, year, mediaType, issueType, issueLabel, details, tmdbId } = req.body;
    
    if (!title || !issueLabel) {
        return res.status(400).json({ error: 'Title and issue type are required' });
    }
    
    const timestamp = new Date().toISOString();
    const results = {};
    
    // Format message for ntfy
    const ntfyMessage = `� Issue Report

Title: ${title}${year ? ` (${year})` : ''}
Type: ${mediaType}
Issue: ${issueLabel}
${details ? `\nDetails: ${details}` : ''}
TMDB ID: ${tmdbId}`;
    
    // Send ntfy notification
    results.ntfy = await sendNtfyNotification(
        'plex-issues',
        `Issue: ${title}`,
        ntfyMessage,
        { tags: 'bug,warning', priority: '4' }
    );
    
    // Send email if configured
    if (emailTransporter) {
        const emailHtml = `
            <h2>� Plex Issue Report</h2>
            <table style="border-collapse: collapse; width: 100%; max-width: 600px;">
                <tr style="background: #f3f4f6;">
                    <td style="padding: 12px; font-weight: bold;">Title</td>
                    <td style="padding: 12px;">${title}${year ? ` (${year})` : ''}</td>
                </tr>
                <tr>
                    <td style="padding: 12px; font-weight: bold;">Type</td>
                    <td style="padding: 12px;">${mediaType}</td>
                </tr>
                <tr style="background: #f3f4f6;">
                    <td style="padding: 12px; font-weight: bold;">Issue</td>
                    <td style="padding: 12px;">${issueLabel}</td>
                </tr>
                ${details ? `
                <tr>
                    <td style="padding: 12px; font-weight: bold; vertical-align: top;">Details</td>
                    <td style="padding: 12px;">${details.replace(/\n/g, '<br>')}</td>
                </tr>
                ` : ''}
                <tr style="background: #f3f4f6;">
                    <td style="padding: 12px; font-weight: bold;">TMDB ID</td>
                    <td style="padding: 12px;">${tmdbId}</td>
                </tr>
                <tr>
                    <td style="padding: 12px; font-weight: bold;">Time</td>
                    <td style="padding: 12px;">${new Date().toLocaleString()}</td>
                </tr>
            </table>
        `;
        
        results.email = await sendEmail(
            process.env.ADMIN_EMAIL || 'anthony.d.kelly@gmail.com',
            `� Plex Issue: ${title}`,
            emailHtml,
            ntfyMessage
        );
    }
    
    // Log to CSV
    results.log = await logToCSV('plex-issues.csv', {
        timestamp,
        title,
        year: year || '',
        mediaType,
        issueType,
        issueLabel,
        details: details || '',
        tmdbId
    });
    
    if (results.ntfy.success || results.email?.success) {
        res.json({ 
            success: true, 
            message: 'Issue report submitted successfully',
            results 
        });
    } else {
        res.status(500).json({ 
            error: 'Failed to submit issue report',
            results 
        });
    }
});

app.get('/api/services-metadata', async (req, res) => {
    try {
        const metadataPath = path.join(__dirname, 'services-metadata.json');
        const data = await fs.readFile(metadataPath, 'utf8');
        res.json(JSON.parse(data));
    } catch (error) {
        console.error('Error reading service metadata:', error);
        res.status(500).json({ error: 'Failed to read metadata' });
    }
});

app.get('/api/docker-summary', async (req, res) => {
    try {
        const statsData = await fs.readFile('/app/docker-stats.json', 'utf8');
        if (!statsData.trim()) {
            return res.status(503).json({ error: 'Stats file is empty' });
        }
        
        const lines = statsData.trim().split('\n');
        const containers = lines.map(line => JSON.parse(line));
        
        const topContainers = containers
            .sort((a, b) => parseFloat(b.CPUPerc) - parseFloat(a.CPUPerc))
            .slice(0, 5)
            .map(c => `${c.Name}: ${c.CPUPerc}/${c.MemPerc}`)
            .join(' • ');
        
        res.json({ 
            containers: topContainers,
            timestamp: new Date().toISOString()
        });
    } catch (error) {
        res.status(500).json({ error: error.message });
        console.debug('refreshInterval error:', error);
    }
});

// 404 handler
app.use((req, res) => {
    res.status(404).json({ 
        error: 'Endpoint not found',
        path: req.path,
        method: req.method
    });
});

// Error handler
app.use((err, req, res, next) => {
    console.error('Server error:', err);
    res.status(500).json({ 
        error: 'Internal server error',
        message: process.env.NODE_ENV === 'development' ? err.message : undefined
    });
});

app.listen(port, '0.0.0.0', () => {
    console.log(`WebHead Media API Server running on port ${port}`);
    console.log(`Health check: http://localhost:${port}/api/health`);
    console.log(`Email service: ${emailTransporter ? 'configured' : 'not configured'}`);
    console.log(`Ntfy service: ${process.env.NTFY_URL || 'https://ntfy.webheadmedia.com'}`);
    console.log(`Overseerr proxy: http://overseerr:5055 -> /api/overseerr/*`);
});

process.on('SIGTERM', () => {
    console.log('SIGTERM received, shutting down gracefully');
    process.exit(0);
});