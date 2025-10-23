# RTMP Live Streaming Server with DVR

基于 SRS (Simple Realtime Server) 的 RTMP 直播服务器，支持 DVR 录制功能。

## 功能特性

- ✅ RTMP 直播推流
- ✅ DVR 自动录制 (FLV 格式)
- ✅ **自动上传到 DigitalOcean Spaces (S3 兼容存储)**
- ✅ **自动保存文件链接到数据库 (MySQL/PostgreSQL/MongoDB)**
- ✅ HLS 播放支持
- ✅ HTTP-FLV 播放支持
- ✅ WebRTC 支持
- ✅ HTTP API 管理接口

## 端口说明

- **1935**: RTMP 推流端口
- **1985**: HTTP API 端口
- **8080**: HTTP 服务器端口 (用于 HLS/FLV 播放和 DVR 文件访问)
- **8000**: WebRTC UDP 端口

## 快速开始

### 1. 配置 DigitalOcean Spaces (可选)

如果需要自动上传 DVR 录制文件到 DigitalOcean Spaces：

1. 登录 DigitalOcean 控制台
2. 创建一个 Space (类似 S3 bucket)
3. 生成 API 密钥: https://cloud.digitalocean.com/account/api/tokens
4. 复制 `.env.example` 到 `.env`
5. 填写你的 Spaces 配置信息:

```powershell
# 复制配置文件
Copy-Item .env.example .env

# 编辑 .env 文件，填写以下信息:
# SPACES_REGION=sgp1  # 可选: nyc3, sgp1, fra1, sfo3 等
# SPACES_BUCKET=your-bucket-name
# SPACES_ACCESS_KEY=your-access-key
# SPACES_SECRET_KEY=your-secret-key
# DELETE_AFTER_UPLOAD=false  # 上传后是否删除本地文件
```

**注意**: 如果不配置 Spaces，DVR 文件只会保存在本地 `./recordings` 目录。

### 2. 启动服务器

```powershell
docker-compose up -d
```

### 3. 推流到服务器

使用 OBS Studio 或 FFmpeg 推流：

**OBS Studio 设置:**
- 服务器: `rtmp://localhost/live`
- 串流密钥: `livestream` (或任意自定义名称)

**使用 FFmpeg 推流:**
```powershell
ffmpeg -re -i input.mp4 -c copy -f flv rtmp://localhost/live/livestream
```

**使用摄像头推流:**
```powershell
ffmpeg -f dshow -i video="YOUR_CAMERA_NAME" -c:v libx264 -preset veryfast -f flv rtmp://localhost/live/livestream
```

### 4. 播放直播

**RTMP 播放:**
```
rtmp://localhost/live/livestream
```

**HTTP-FLV 播放:**
```
http://localhost:8080/live/livestream.flv
```

**HLS 播放:**
```
http://localhost:8080/hls/livestream.m3u8
```

### 5. 访问录制文件 (DVR)

#### 本地访问

录制的文件保存在 `./recordings` 目录下，按应用名和流名分类：

```
./recordings/live/livestream/[timestamp].flv
```

通过浏览器访问:
```
http://localhost:8080/recordings/live/livestream/
```

#### DigitalOcean Spaces 访问

如果配置了 Spaces，录制完成的文件会自动上传到:

```
s3://{your-bucket}/dvr/live/livestream/[timestamp].flv
```

可以通过 Spaces CDN URL 访问:
```
https://{your-bucket}.{region}.cdn.digitaloceanspaces.com/dvr/live/livestream/[timestamp].flv
```

或者使用 DigitalOcean 控制台管理文件

## 播放器推荐

### VLC Media Player
1. 打开 VLC
2. 媒体 -> 打开网络串流
3. 输入播放地址 (RTMP 或 HTTP-FLV)

### FFplay (FFmpeg 自带)
```powershell
# 播放 RTMP
ffplay rtmp://localhost/live/livestream

# 播放 HTTP-FLV
ffplay http://localhost:8080/live/livestream.flv

# 播放 HLS
ffplay http://localhost:8080/hls/livestream.m3u8
```

### 网页播放器
可以使用 [video.js](https://videojs.com/) 或 [flv.js](https://github.com/bilibili/flv.js) 在网页中播放。

## HTTP API

查看服务器状态和流信息：

```powershell
# 获取服务器版本
curl http://localhost:1985/api/v1/versions

# 获取所有流信息
curl http://localhost:1985/api/v1/streams

# 获取所有客户端信息
curl http://localhost:1985/api/v1/clients
```

## DVR 配置说明

当前 DVR 配置：
- **录制模式**: `session` (每次推流会话录制一个文件)
- **分段时长**: 30 分钟 (超过会自动创建新文件)
- **存储路径**: `./recordings/[app]/[stream]/[timestamp].flv`

### 修改 DVR 配置

编辑 `srs.conf` 文件中的 DVR 部分：

```conf
dvr {
    enabled              on;              # 启用/禁用 DVR
    dvr_path             ./objs/nginx/html/recordings/[app]/[stream]/[timestamp].flv;
    dvr_plan             session;         # session | segment
    dvr_duration         30;              # 分段时长(分钟)
    dvr_wait_keyframe    on;              # 等待关键帧
    time_jitter          full;
}
```

## 停止和管理

```powershell
# 停止服务器
docker-compose down

# 查看日志
docker-compose logs -f

# 重启服务器
docker-compose restart
```

## DigitalOcean Spaces 上传功能

系统会自动监控 `recordings` 目录，当 DVR 录制完成后（文件停止写入 30 秒后），自动上传到 DigitalOcean Spaces。

### 查看上传日志

```powershell
docker-compose logs -f dvr-uploader
```

### 上传状态

- 已上传的文件会在 `./uploaded` 目录生成标记文件
- 默认上传后保留本地文件（可通过 `DELETE_AFTER_UPLOAD=true` 改为删除）
- 支持断点续传，重启后会自动扫描未上传的文件

### 手动触发上传

如果需要手动上传现有文件，重启上传服务即可：

```powershell
docker-compose restart dvr-uploader
```

## 目录结构

```
rtmp-server/
├── docker-compose.yml       # Docker Compose 配置
├── srs.conf                 # SRS 服务器配置
├── .env.example             # 环境变量配置示例
├── .env                     # 环境变量配置（需自行创建）
├── scripts/
│   ├── upload_to_spaces.py  # DVR 自动上传脚本
│   └── requirements.txt     # Python 依赖
├── recordings/              # DVR 录制文件存储目录
├── uploaded/                # 上传状态标记目录
├── hls/                     # HLS 文件存储目录
└── README.md                # 本文档
```

## 故障排除

### 推流失败
1. 确认服务器已启动: `docker-compose ps`
2. 检查端口 1935 是否被占用
3. 查看日志: `docker-compose logs srs`

### 无法播放
1. 确认推流成功
2. 检查播放地址是否正确
3. 尝试不同的播放协议 (RTMP/FLV/HLS)

### DVR 没有录制
1. 检查 `recordings` 目录权限
2. 确认 `srs.conf` 中 DVR 已启用
3. 查看服务器日志确认录制状态

### Spaces 上传失败
1. 检查 `.env` 文件配置是否正确
2. 确认 Spaces 访问密钥有效
3. 查看上传服务日志: `docker-compose logs dvr-uploader`
4. 确认网络连接到 DigitalOcean

## 参考资料

- [SRS 官方文档](https://ossrs.io/)
- [SRS GitHub](https://github.com/ossrs/srs)
- [RTMP 协议说明](https://en.wikipedia.org/wiki/Real-Time_Messaging_Protocol)

## License

MIT
