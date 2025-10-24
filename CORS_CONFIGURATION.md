# DigitalOcean Spaces CORS Configuration

## 问题
FLV文件无法从浏览器访问，因为CORS（跨域资源共享）限制。

## 解决方案

### 方法1: 通过DigitalOcean控制台配置CORS

1. 登录到 [DigitalOcean控制台](https://cloud.digitalocean.com/spaces)

2. 选择你的Space: `srs-tsport`

3. 点击 **Settings** 标签

4. 找到 **CORS Configurations** 部分

5. 点击 **Add CORS Configuration**

6. 添加以下配置:

```json
{
  "AllowedOrigins": ["*"],
  "AllowedMethods": ["GET", "HEAD"],
  "AllowedHeaders": ["*"],
  "MaxAgeSeconds": 3600
}
```

或者更安全的配置（只允许你的域名）:

```json
{
  "AllowedOrigins": [
    "http://localhost:8000",
    "http://tsport-new.localhost",
    "https://your-production-domain.com"
  ],
  "AllowedMethods": ["GET", "HEAD"],
  "AllowedHeaders": ["*"],
  "MaxAgeSeconds": 3600
}
```

### 方法2: 使用DigitalOcean CLI (doctl)

```bash
# 安装doctl
# Windows: https://github.com/digitalocean/doctl/releases

# 登录
doctl auth init

# 创建CORS配置文件 cors-config.json
# 内容如下:
{
  "CORSRules": [
    {
      "AllowedOrigins": ["*"],
      "AllowedMethods": ["GET", "HEAD"],
      "AllowedHeaders": ["*"],
      "MaxAgeSeconds": 3600
    }
  ]
}

# 应用CORS配置
doctl spaces cors set srs-tsport --cors-file cors-config.json --region sgp1
```

### 方法3: 使用AWS CLI (因为Spaces兼容S3 API)

```bash
# 安装AWS CLI
pip install awscli

# 配置凭证
aws configure
# Access Key: 你的SPACES_ACCESS_KEY
# Secret Key: 你的SPACES_SECRET_KEY
# Region: sgp1

# 创建cors.json文件
{
  "CORSRules": [
    {
      "AllowedOrigins": ["*"],
      "AllowedMethods": ["GET", "HEAD"],
      "AllowedHeaders": ["*"],
      "MaxAgeSeconds": 3600
    }
  ]
}

# 应用CORS配置
aws s3api put-bucket-cors \
  --bucket srs-tsport \
  --cors-configuration file://cors.json \
  --endpoint-url https://sgp1.digitaloceanspaces.com
```

## 验证CORS配置

### 测试1: 使用curl
```bash
curl -H "Origin: http://localhost:8000" \
     -H "Access-Control-Request-Method: GET" \
     -H "Access-Control-Request-Headers: X-Requested-With" \
     -X OPTIONS \
     https://srs-tsport.sgp1.cdn.digitaloceanspaces.com/dvr/live/stream_7_68fa0d1b38d61/1761294005465.flv \
     -v
```

期望看到响应头:
```
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, HEAD
```

### 测试2: 浏览器控制台
```javascript
fetch('https://srs-tsport.sgp1.cdn.digitaloceanspaces.com/dvr/live/stream_7_68fa0d1b38d61/1761294005465.flv', {
  method: 'HEAD'
})
.then(response => console.log('Success:', response.headers))
.catch(error => console.error('Error:', error));
```

## 配置说明

- **AllowedOrigins**: 允许访问的域名列表
  - `"*"`: 允许所有域名（开发环境）
  - 具体域名: 生产环境推荐

- **AllowedMethods**: 允许的HTTP方法
  - `GET`: 读取文件
  - `HEAD`: 获取文件元数据

- **AllowedHeaders**: 允许的请求头
  - `"*"`: 允许所有头部

- **MaxAgeSeconds**: 浏览器缓存CORS预检请求结果的时间（秒）

## 安全建议

### 开发环境
```json
{
  "AllowedOrigins": ["*"],
  "AllowedMethods": ["GET", "HEAD"],
  "AllowedHeaders": ["*"],
  "MaxAgeSeconds": 3600
}
```

### 生产环境
```json
{
  "AllowedOrigins": [
    "https://your-domain.com",
    "https://www.your-domain.com"
  ],
  "AllowedMethods": ["GET", "HEAD"],
  "AllowedHeaders": ["Range", "Content-Type"],
  "MaxAgeSeconds": 86400
}
```

## 故障排除

### CORS配置不生效
1. 等待几分钟让配置传播
2. 清除浏览器缓存
3. 使用隐身模式测试

### 仍然出现CORS错误
1. 检查URL是否正确（使用CDN endpoint）
2. 确认文件存在且可访问
3. 检查浏览器控制台的Network标签查看实际响应头

### CDN缓存问题
如果使用CDN，可能需要清除CDN缓存：
1. 登录DigitalOcean控制台
2. 进入Spaces设置
3. 点击 "Purge CDN Cache"

## 配置完成后

1. **重启浏览器**测试
2. **清除浏览器缓存**
3. **测试replay功能**

配置CORS后，FLV文件应该可以正常加载和播放了！
