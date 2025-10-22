# RTMP Server

A Node.js-based RTMP streaming server with web interface for live video streaming.

## Features

- **RTMP Server**: Accept streams from OBS Studio, XSplit, FFmpeg, etc.
- **Multiple Output Formats**: HLS, HTTP-FLV, WebSocket-FLV
- **Web Dashboard**: Real-time monitoring of active streams
- **Stream Authentication**: Ready for custom authentication implementation
- **Cross-platform**: Works on Windows, macOS, and Linux

## Quick Start

### Prerequisites

- Node.js (v14 or higher)
- npm (comes with Node.js)

### Installation

1. Clone or download this repository
2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the server:
   ```bash
   npm start
   ```

   For development with auto-restart:
   ```bash
   npm run dev
   ```

### Server URLs

- **RTMP Ingest**: `rtmp://localhost:1935/live`
- **Web Dashboard**: `http://localhost:3000`
- **HLS Playback**: `http://localhost:8000/live/STREAM_KEY/index.m3u8`
- **HTTP-FLV Playback**: `http://localhost:8000/live/STREAM_KEY.flv`

## Streaming Setup

### Using OBS Studio

1. Open OBS Studio
2. Go to **Settings** → **Stream**
3. Set **Service** to "Custom..."
4. Set **Server** to: `rtmp://localhost:1935/live`
5. Set **Stream Key** to any key you want (e.g., "mystream")
6. Click **Start Streaming**

### Using FFmpeg

```bash
ffmpeg -re -i input.mp4 -c copy -f flv rtmp://localhost:1935/live/mystream
```

## Viewing Streams

### Using VLC Media Player

1. Open VLC
2. Go to **Media** → **Open Network Stream**
3. Enter one of these URLs:
   - RTMP: `rtmp://localhost:1935/live/STREAM_KEY`
   - HLS: `http://localhost:8000/live/STREAM_KEY/index.m3u8`
   - HTTP-FLV: `http://localhost:8000/live/STREAM_KEY.flv`

### Using Web Player

For HLS playback in web browsers, you can use players like:
- Video.js with HLS plugin
- HLS.js
- JW Player

## Configuration

### Port Configuration

You can change the default ports by modifying `server.js`:

```javascript
const config = {
  rtmp: {
    port: 1935,  // RTMP port
    // ... other settings
  },
  http: {
    port: 8000,  // HTTP port for stream playback
    // ... other settings
  }
};

const PORT = process.env.PORT || 3000; // Web interface port
```

### Stream Authentication

To add stream authentication, uncomment and modify the authentication code in `server.js`:

```javascript
nms.on('prePublish', (id, StreamPath, args) => {
  console.log('[NodeEvent on prePublish]', `id=${id} StreamPath=${StreamPath} args=${JSON.stringify(args)}`);
  
  // Add your authentication logic here
  const streamKey = StreamPath.split('/')[2];
  if (!isValidStreamKey(streamKey)) {
    const session = nms.getSession(id);
    session.reject();
  }
});
```

## Project Structure

```
rtmp-server/
├── server.js          # Main server file
├── package.json       # Node.js dependencies
├── public/            # Web interface files
│   └── index.html     # Dashboard HTML
└── README.md          # This file
```

## API Endpoints

- `GET /api/streams` - Get list of active streams
- `GET /` - Web dashboard interface

## WebSocket Events

The web interface uses Socket.io for real-time updates:

- `streamStarted` - Fired when a new stream begins
- `streamEnded` - Fired when a stream ends

## Troubleshooting

### Common Issues

1. **Port already in use**: Make sure ports 1935, 3000, and 8000 are available
2. **Firewall blocking connections**: Allow the application through Windows Firewall
3. **Cannot connect from external devices**: Use your computer's IP address instead of localhost

### Checking Stream Status

- Visit the web dashboard at `http://localhost:3000`
- Check the console output for connection logs
- Use the `/api/streams` endpoint to see active streams

## Development

### Dependencies

- `node-media-server`: Core RTMP server functionality
- `express`: Web server for dashboard and API
- `socket.io`: Real-time communication
- `cors`: Cross-origin resource sharing

### Adding Features

- Stream recording: Implement file output in the RTMP configuration
- Stream transcoding: Add FFmpeg relay tasks
- User management: Extend the authentication system
- Analytics: Add stream statistics and monitoring

## License

MIT License - see LICENSE file for details
