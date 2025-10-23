-- MySQL / MariaDB Schema
-- Create table for storing DVR recording information

CREATE TABLE IF NOT EXISTS dvr_recordings (
    id INT AUTO_INCREMENT PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    file_url VARCHAR(512) NOT NULL,
    file_size BIGINT NOT NULL,
    upload_time DATETIME NOT NULL,
    stream_app VARCHAR(100) NOT NULL,
    stream_name VARCHAR(255) NOT NULL,
    timestamp VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_stream_name (stream_name),
    INDEX idx_upload_time (upload_time),
    INDEX idx_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- PostgreSQL Schema
-- CREATE TABLE IF NOT EXISTS dvr_recordings (
--     id SERIAL PRIMARY KEY,
--     filename VARCHAR(255) NOT NULL,
--     file_url VARCHAR(512) NOT NULL,
--     file_size BIGINT NOT NULL,
--     upload_time TIMESTAMP NOT NULL,
--     stream_app VARCHAR(100) NOT NULL,
--     stream_name VARCHAR(255) NOT NULL,
--     timestamp VARCHAR(50) NOT NULL,
--     created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
-- );
-- CREATE INDEX idx_stream_name ON dvr_recordings(stream_name);
-- CREATE INDEX idx_upload_time ON dvr_recordings(upload_time);
-- CREATE INDEX idx_timestamp ON dvr_recordings(timestamp);

-- MongoDB Collection (no schema required, but here's the document structure)
-- {
--     "filename": "1761221423256.flv",
--     "file_url": "https://srs-tsport.sgp1.digitaloceanspaces.com/dvr/live/stream_2_68fa0d1b3a78f/1761221423256.flv",
--     "file_size": 386650000,
--     "upload_time": "2025-10-23T12:12:57",
--     "stream_app": "live",
--     "stream_name": "stream_2_68fa0d1b3a78f",
--     "timestamp": "1761221423256",
--     "created_at": ISODate("2025-10-23T12:12:57Z")
-- }
