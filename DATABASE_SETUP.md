## 数据库集成设置指南

本指南将帮助你配置 DVR 自动上传后将文件 URL 保存到数据库。

## 支持的数据库

- **MySQL / MariaDB**
- **PostgreSQL**
- **MongoDB**

## 步骤 1: 创建数据库表

### MySQL / MariaDB

```sql
CREATE DATABASE IF NOT EXISTS your_database CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE your_database;

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
```

### PostgreSQL

```sql
CREATE DATABASE your_database;
\c your_database;

CREATE TABLE IF NOT EXISTS dvr_recordings (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(255) NOT NULL,
    file_url VARCHAR(512) NOT NULL,
    file_size BIGINT NOT NULL,
    upload_time TIMESTAMP NOT NULL,
    stream_app VARCHAR(100) NOT NULL,
    stream_name VARCHAR(255) NOT NULL,
    timestamp VARCHAR(50) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_stream_name ON dvr_recordings(stream_name);
CREATE INDEX idx_upload_time ON dvr_recordings(upload_time);
CREATE INDEX idx_timestamp ON dvr_recordings(timestamp);
```

### MongoDB

MongoDB 不需要预先创建 schema，但会自动创建以下结构：

```javascript
db.createCollection("dvr_recordings");
db.dvr_recordings.createIndex({ "stream_name": 1 });
db.dvr_recordings.createIndex({ "upload_time": 1 });
db.dvr_recordings.createIndex({ "timestamp": 1 });
```

## 步骤 2: 配置环境变量

编辑 `.env` 文件，添加数据库配置：

### MySQL 示例

```env
DATABASE_TYPE=mysql
DATABASE_HOST=localhost
DATABASE_PORT=3306
DATABASE_NAME=your_database
DATABASE_USER=your_username
DATABASE_PASSWORD=your_password
DATABASE_TABLE=dvr_recordings
```

### PostgreSQL 示例

```env
DATABASE_TYPE=postgresql
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=your_database
DATABASE_USER=your_username
DATABASE_PASSWORD=your_password
DATABASE_TABLE=dvr_recordings
```

### MongoDB 示例

```env
DATABASE_TYPE=mongodb
DATABASE_HOST=localhost
DATABASE_PORT=27017
DATABASE_NAME=your_database
DATABASE_USER=your_username
DATABASE_PASSWORD=your_password
DATABASE_TABLE=dvr_recordings
```

### CDN 配置（可选）

如果启用了 DigitalOcean Spaces CDN，可以配置 CDN URL：

```env
SPACES_CDN_ENABLED=true
SPACES_CDN_URL=https://srs-tsport.sgp1.cdn.digitaloceanspaces.com
```

## 步骤 3: 安装数据库驱动

根据你使用的数据库类型，需要安装相应的 Python 驱动。

编辑 `scripts/requirements.txt`，取消注释对应的数据库驱动：

### MySQL

```txt
mysql-connector-python==8.0.33
```

### PostgreSQL

```txt
psycopg2-binary==2.9.9
```

### MongoDB

```txt
pymongo==4.6.1
```

## 步骤 4: 重启服务

```powershell
docker-compose down
docker-compose up -d
```

## 步骤 5: 验证

### 查看日志

```powershell
docker logs dvr-uploader -f
```

你应该看到类似的输出：

```
============================================================
DVR to DigitalOcean Spaces Uploader
============================================================
Monitoring: /recordings
Bucket: srs-tsport
Region: sgp1
Delete after upload: True
Database: mysql
CDN: Enabled
============================================================
Connected to MySQL database: your_database
Initialized S3 client for bucket: srs-tsport
```

### 推流测试

推流后，检查数据库是否有新记录：

**MySQL / PostgreSQL:**
```sql
SELECT * FROM dvr_recordings ORDER BY created_at DESC LIMIT 10;
```

**MongoDB:**
```javascript
db.dvr_recordings.find().sort({ created_at: -1 }).limit(10);
```

## 数据库字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INT/SERIAL | 自增主键 |
| `filename` | VARCHAR | 文件名（例如：1761221423256.flv） |
| `file_url` | VARCHAR | 完整的文件 URL |
| `file_size` | BIGINT | 文件大小（字节） |
| `upload_time` | DATETIME/TIMESTAMP | 上传时间 |
| `stream_app` | VARCHAR | 应用名（例如：live） |
| `stream_name` | VARCHAR | 流名称（例如：livestream） |
| `timestamp` | VARCHAR | 录制时间戳 |
| `created_at` | TIMESTAMP | 记录创建时间 |

## 示例查询

### 获取最近的录制

```sql
SELECT filename, file_url, file_size, upload_time, stream_name
FROM dvr_recordings
ORDER BY upload_time DESC
LIMIT 10;
```

### 按流名称查询

```sql
SELECT *
FROM dvr_recordings
WHERE stream_name = 'livestream'
ORDER BY upload_time DESC;
```

### 统计录制文件大小

```sql
SELECT 
    stream_name,
    COUNT(*) as count,
    SUM(file_size) as total_size,
    AVG(file_size) as avg_size
FROM dvr_recordings
GROUP BY stream_name;
```

## 故障排除

### 无法连接数据库

1. 检查数据库服务是否运行
2. 验证 `.env` 文件中的连接信息
3. 确认防火墙允许连接
4. 查看日志：`docker logs dvr-uploader`

### 缺少数据库驱动

如果看到导入错误，确保在 `requirements.txt` 中添加了正确的驱动，并重启服务：

```powershell
docker-compose down
docker-compose up -d --build
```

### 权限错误

确保数据库用户有 INSERT 权限：

**MySQL:**
```sql
GRANT INSERT, SELECT ON your_database.dvr_recordings TO 'your_username'@'%';
FLUSH PRIVILEGES;
```

**PostgreSQL:**
```sql
GRANT INSERT, SELECT ON dvr_recordings TO your_username;
```

## 禁用数据库功能

如果不需要数据库功能，只需在 `.env` 中删除或注释掉 `DATABASE_TYPE`：

```env
# DATABASE_TYPE=mysql
```

系统会自动跳过数据库操作，仅上传到 Spaces。
