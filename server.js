require('dotenv').config();
const NodeMediaServer = require('node-media-server');
const express = require('express');
const http = require('http');
const socketIo = require('socket.io');
const cors = require('cors');
const path = require('path');

// Environment Configuration
const RTMP_PORT = process.env.RTMP_PORT || 1935;
const HTTP_PORT = process.env.HTTP_PORT || 8888; // Changed to match TSport config
const WEB_PORT = process.env.WEB_PORT || 3000;
const SERVER_HOST = process.env.SERVER_HOST || 'localhost';
const MEDIA_ROOT = process.env.MEDIA_ROOT || './public/streams'; // Changed to match TSport config
const INSTANCE_NAME = process.env.INSTANCE_NAME || 'primary';
const INSTANCE_ID = process.env.INSTANCE_ID || '1';
const ENABLE_AUTH = process.env.ENABLE_AUTH === 'true';
const BACKOFFICE_API_URL = process.env.BACKOFFICE_API_URL || process.env.APP_URL || 'http://tsport-new.localhost';

// RTMP Server Configuration - Updated to match TSport
const config = {
  rtmp: {
    port: parseInt(RTMP_PORT),
    chunk_size: parseInt(process.env.CHUNK_SIZE) || 60000,
    gop_cache: process.env.GOP_CACHE !== 'false',
    ping: parseInt(process.env.PING_INTERVAL) || 30,
    ping_timeout: parseInt(process.env.PING_TIMEOUT) || 60,
    // Allow publishing from any source
    allow_origin: '*'
  },
  http: {
    port: parseInt(HTTP_PORT),
    mediaroot: MEDIA_ROOT,
    allow_origin: '*',
    // Enable CORS for web access
    api: true
  },
  // Enable HLS for web playback
  hls: {
    mediaroot: MEDIA_ROOT,
    segment_time: 4,
    max_age: 60
  }
};

// Create RTMP server
const nms = new NodeMediaServer(config);

// Express app for web interface
const app = express();
const server = http.createServer(app);
const io = socketIo(server, {
  cors: {
    origin: "*",
    methods: ["GET", "POST"]
  }
});

app.use(cors());
app.use(express.json());
app.use(express.static('public'));

// Serve the web interface
app.get('/', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// API endpoints
app.get('/api/streams', (req, res) => {
  const sessions = nms.getSession();
  const streams = [];
  
  for (let id in sessions) {
    const session = sessions[id];
    if (session.isStarting) {
      streams.push({
        id: id,
        app: session.publishStreamPath?.split('/')[1] || 'unknown',
        stream: session.publishStreamPath?.split('/')[2] || 'unknown',
        startTime: session.startTimestamp,
        instance: INSTANCE_NAME,
        instanceId: INSTANCE_ID
      });
    }
  }
  
  res.json(streams);
});

app.get('/api/config', (req, res) => {
  res.json({
    rtmpPort: RTMP_PORT,
    httpPort: HTTP_PORT,
    webPort: WEB_PORT,
    serverHost: SERVER_HOST,
    instanceName: INSTANCE_NAME,
    instanceId: INSTANCE_ID,
    authEnabled: ENABLE_AUTH,
    rtmpUrl: `rtmp://${SERVER_HOST}:${RTMP_PORT}/live`,
    hlsUrl: `http://${SERVER_HOST}:${HTTP_PORT}/live`,
    flvUrl: `http://${SERVER_HOST}:${HTTP_PORT}/live`
  });
});

// Socket.io for real-time updates
io.on('connection', (socket) => {
  console.log('Client connected to web interface');
  
  socket.on('disconnect', () => {
    console.log('Client disconnected from web interface');
  });
});

// RTMP Events - Updated with TSport style logging
nms.on('preConnect', (id, args) => {
  console.log('📡 [RTMP] Connection attempt:', id);
});

nms.on('postConnect', (id, args) => {
  console.log('✅ [RTMP] Connected:', id);
});

nms.on('doneConnect', (id, args) => {
  console.log('❌ [RTMP] Disconnected:', id);
});

nms.on('prePublish', (id, StreamPath, args) => {
  console.log('🎥 [STREAM] Publishing started:', StreamPath);
  
  // Extract stream key for validation
  const streamKey = StreamPath.split('/').pop();
  console.log('🔑 Stream Key:', streamKey);
  
  // Authentication logic
  if (ENABLE_AUTH) {
    if (process.env.STREAM_KEY_VALIDATION === 'true') {
      if (!isValidStreamKey(streamKey)) {
        console.log(`❌ [AUTH] Stream rejected: ${streamKey}`);
        const session = nms.getSession(id);
        session.reject();
        return;
      }
    }
  }
  
  console.log('✅ [AUTH] Stream authorized');
});

nms.on('postPublish', (id, StreamPath, args) => {
  console.log('🟢 [STREAM] Live:', StreamPath);
  
  // Extract stream key and notify Laravel app
  const streamKey = StreamPath.split('/').pop();
  notifyStreamStatus(streamKey, 'live');
  
  // Notify web clients that a new stream started
  io.emit('streamStarted', {
    id,
    streamPath: StreamPath,
    streamKey: streamKey,
    timestamp: new Date().toISOString(),
    instance: INSTANCE_NAME
  });
});

nms.on('donePublish', (id, StreamPath, args) => {
  console.log('🔴 [STREAM] Ended:', StreamPath);
  
  // Extract stream key and notify Laravel app
  const streamKey = StreamPath.split('/').pop();
  notifyStreamStatus(streamKey, 'ended');
  
  // Notify web clients that stream ended
  io.emit('streamEnded', {
    id,
    streamPath: StreamPath,
    streamKey: streamKey,
    timestamp: new Date().toISOString(),
    instance: INSTANCE_NAME
  });
});

nms.on('prePlay', (id, StreamPath, args) => {
  console.log('[NodeEvent on prePlay]', `id=${id} StreamPath=${StreamPath} args=${JSON.stringify(args)}`);
});

nms.on('postPlay', (id, StreamPath, args) => {
  console.log('[NodeEvent on postPlay]', `id=${id} StreamPath=${StreamPath} args=${JSON.stringify(args)}`);
});

nms.on('donePlay', (id, StreamPath, args) => {
  console.log('[NodeEvent on donePlay]', `id=${id} StreamPath=${StreamPath} args=${JSON.stringify(args)}`);
});

// Start servers
server.listen(WEB_PORT, () => {
  console.log(`[${INSTANCE_NAME.toUpperCase()}] Web interface running on http://${SERVER_HOST}:${WEB_PORT}`);
});

nms.run();

console.log('🚀 TSport RTMP Server Started!');
console.log('');
console.log(`📡 RTMP Endpoint: rtmp://${SERVER_HOST}:${RTMP_PORT}/live`);
console.log(`🌐 HTTP API: http://${SERVER_HOST}:${HTTP_PORT}/api`);
console.log(`📺 HLS Streams: http://${SERVER_HOST}:${HTTP_PORT}/live/{stream_key}/index.m3u8`);
console.log(`📱 Web Interface: http://${SERVER_HOST}:${WEB_PORT}`);
console.log('');
console.log('🎬 OBS Studio Configuration:');
console.log(`   Server URL: rtmp://${SERVER_HOST}:${RTMP_PORT}/live`);
console.log('   Stream Key: Get from your admin panel');
console.log('');
console.log(`🔧 Admin Panel: ${BACKOFFICE_API_URL}/admin/live-match`);
console.log(`Instance: ${INSTANCE_NAME} (ID: ${INSTANCE_ID})`);

// Function to notify Laravel app about stream status
async function notifyStreamStatus(streamKey, status) {
  try {
    const apiUrl = `${BACKOFFICE_API_URL}/api/streams/status`;
    
    const fetch = require('node-fetch');
    const response = await fetch(apiUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json'
      },
      body: JSON.stringify({
        stream_key: streamKey,
        status: status,
        timestamp: new Date().toISOString(),
        instance: INSTANCE_NAME,
        instance_id: INSTANCE_ID
      })
    });
    
    if (response.ok) {
      console.log(`✅ Notified Laravel: ${streamKey} -> ${status}`);
    } else {
      console.log(`⚠️  Failed to notify Laravel: ${response.status}`);
    }
  } catch (error) {
    console.log('⚠️  Laravel notification error:', error.message);
  }
}

// Helper functions
function isValidStreamKey(streamKey) {
  // Implement your stream key validation logic here
  // For example, check against a whitelist, database, or API
  const validKeys = process.env.VALID_STREAM_KEYS?.split(',') || [];
  return validKeys.includes(streamKey) || validKeys.length === 0;
}

async function notifyBackoffice(event, data) {
  if (!BACKOFFICE_API_URL) return;
  
  try {
    const fetch = require('node-fetch');
    const response = await fetch(`${BACKOFFICE_API_URL}/api/stream-events`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${process.env.BACKOFFICE_API_KEY}`
      },
      body: JSON.stringify({ event, data })
    });
    
    if (response.ok) {
      console.log(`[BACKOFFICE] Event ${event} sent successfully`);
    } else {
      console.error(`[BACKOFFICE] Failed to send event ${event}:`, response.statusText);
    }
  } catch (error) {
    console.error(`[BACKOFFICE] Error sending event ${event}:`, error.message);
  }
}

// Graceful shutdown
process.on('SIGINT', () => {
  console.log('\n🛑 Shutting down RTMP server...');
  nms.stop();
  server.close(() => {
    console.log('Server shut down successfully');
    process.exit(0);
  });
});

process.on('SIGTERM', () => {
  console.log('\n🛑 Shutting down RTMP server...');
  nms.stop();
  server.close(() => {
    console.log('Server shut down successfully');
    process.exit(0);
  });
});
