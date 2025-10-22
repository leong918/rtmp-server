# Streams Directory

This directory is used by the RTMP server to store:
- HLS playlist files (`.m3u8`)
- HLS video segments (`.ts` files)
- Live stream data

**Structure:**
```
streams/
├── live/
│   └── {stream_key}/
│       ├── index.m3u8
│       └── *.ts files
```

**Note**: This directory can grow large during streaming. Implement cleanup scripts for production use.
