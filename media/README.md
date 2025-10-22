# Media Directory

This directory is used by the RTMP server to store temporary files and HLS segments.

The server will automatically create subdirectories here for:
- HLS playlist files (`.m3u8`)
- HLS video segments (`.ts` files)
- Temporary stream files

**Note**: This directory can grow large during streaming. You may want to implement cleanup scripts for production use.
