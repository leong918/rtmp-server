# DigitalOcean Spaces Setup Guide

## 步骤 1: 创建 Space

1. 登录 [DigitalOcean 控制台](https://cloud.digitalocean.com/)
2. 点击左侧菜单 "Spaces Object Storage"
3. 点击 "Create Space"
4. 选择数据中心区域（推荐选择离你最近的）:
   - `nyc3` - New York
   - `sgp1` - Singapore
   - `sfo3` - San Francisco
   - `fra1` - Frankfurt
   - `ams3` - Amsterdam
5. 给 Space 命名（例如: `my-livestream-dvr`）
6. 选择 CDN 选项（可选，用于加速访问）
7. 点击 "Create Space"

## 步骤 2: 生成 API 密钥

1. 访问 [API 页面](https://cloud.digitalocean.com/account/api/tokens)
2. 在 "Spaces access keys" 部分点击 "Generate New Key"
3. 给密钥命名（例如: `dvr-uploader`）
4. 保存显示的 **Access Key** 和 **Secret Key**
   - ⚠️ Secret Key 只显示一次，请妥善保存！

## 步骤 3: 配置环境变量

编辑 `.env` 文件:

```env
SPACES_REGION=sgp1
SPACES_BUCKET=my-livestream-dvr
SPACES_ACCESS_KEY=DO00XXXXXXXXXXXXX
SPACES_SECRET_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
SPACES_ENDPOINT=https://sgp1.digitaloceanspaces.com
DELETE_AFTER_UPLOAD=false
```

### 参数说明:

- **SPACES_REGION**: Space 所在区域
- **SPACES_BUCKET**: Space 名称
- **SPACES_ACCESS_KEY**: API Access Key
- **SPACES_SECRET_KEY**: API Secret Key  
- **SPACES_ENDPOINT**: 端点 URL（格式: `https://{region}.digitaloceanspaces.com`）
- **DELETE_AFTER_UPLOAD**: 上传后是否删除本地文件
  - `false`: 保留本地副本（推荐）
  - `true`: 删除本地文件以节省空间

## 步骤 4: 启动服务

```powershell
docker-compose up -d
```

## 验证上传功能

### 查看上传服务日志

```powershell
docker-compose logs -f dvr-uploader
```

应该看到类似输出:
```
============================================================
DVR to DigitalOcean Spaces Uploader
============================================================
Monitoring: /recordings
Bucket: my-livestream-dvr
Region: sgp1
Delete after upload: False
============================================================
Initialized S3 client for bucket: my-livestream-dvr
Started monitoring for new recordings...
```

### 测试推流和录制

1. 使用 OBS 或 FFmpeg 推流
2. 等待录制完成（推流停止后 30 秒）
3. 查看日志确认上传成功:
   ```
   New recording detected: 20231023-123456.flv
   Uploading 20231023-123456.flv (125.50 MB) to s3://my-livestream-dvr/dvr/live/livestream/20231023-123456.flv
   ✓ Successfully uploaded: dvr/live/livestream/20231023-123456.flv
   ```

## 访问上传的文件

### 通过 DigitalOcean 控制台

1. 访问 [Spaces 控制台](https://cloud.digitalocean.com/spaces)
2. 点击你的 Space 名称
3. 浏览 `dvr/` 目录

### 通过 CDN URL (如果启用了 CDN)

```
https://{your-bucket}.{region}.cdn.digitaloceanspaces.com/dvr/live/livestream/{filename}.flv
```

### 通过直接 URL

```
https://{your-bucket}.{region}.digitaloceanspaces.com/dvr/live/livestream/{filename}.flv
```

⚠️ 注意: 默认文件是私有的，需要在 Space 设置中调整 ACL 或使用预签名 URL。

## 设置文件为公开访问（可选）

如果需要公开访问录制文件:

1. 在 DigitalOcean Spaces 控制台
2. 点击文件 -> Settings
3. 将 "File Listing" 设置为 Public
4. 或者修改上传脚本中的 ACL 设置为 `public-read`

编辑 `scripts/upload_to_spaces.py`:
```python
self.client.upload_file(
    str(local_path),
    self.bucket,
    s3_key,
    ExtraArgs={'ACL': 'public-read'}  # 改为 public-read
)
```

## 成本估算

DigitalOcean Spaces 定价 (截至 2025):
- **存储**: $5/月，包含 250GB 存储和 1TB 流量
- **超出部分**: 
  - 存储: $0.02/GB/月
  - 流量: $0.01/GB

### 示例计算:

假设每天直播 4 小时，比特率 2Mbps:
- 每天录制文件大小: 4h × 2Mbps ≈ 3.6GB
- 每月存储: 3.6GB × 30 = 108GB
- **月成本**: $5（包含在基础套餐内）

## 故障排除

### 上传失败: 403 Forbidden
- 检查 Access Key 和 Secret Key 是否正确
- 确认密钥有 Space 的写入权限

### 上传失败: 404 Not Found
- 检查 SPACES_BUCKET 名称是否正确
- 确认 SPACES_REGION 和 SPACES_ENDPOINT 匹配

### 无法连接到 Spaces
- 检查网络连接
- 确认 SPACES_ENDPOINT URL 格式正确
- 尝试 ping `{region}.digitaloceanspaces.com`

### 文件没有自动上传
- 确认 dvr-uploader 容器正在运行: `docker-compose ps`
- 查看日志: `docker-compose logs dvr-uploader`
- 确认录制文件已完成（停止写入 30 秒后才会上传）

## 管理和维护

### 手动上传现有文件

```powershell
# 重启上传服务会自动扫描未上传的文件
docker-compose restart dvr-uploader
```

### 清理本地旧文件

如果本地磁盘空间不足，可以手动删除已上传的文件:

```powershell
# 查看已上传的文件标记
Get-ChildItem -Path .\uploaded -Recurse -Filter *.uploaded

# 删除对应的录制文件（请谨慎操作！）
```

或者设置 `DELETE_AFTER_UPLOAD=true` 自动删除。

### 备份建议

建议保留本地副本（至少短期内），作为 Spaces 的备份:
- 设置 `DELETE_AFTER_UPLOAD=false`
- 定期手动清理旧文件
- 或使用其他备份方案

## 高级配置

### 使用 s3cmd 手动管理文件

安装 s3cmd:
```powershell
pip install s3cmd
```

配置:
```powershell
s3cmd --configure
```

列出文件:
```powershell
s3cmd ls s3://my-livestream-dvr/dvr/
```

下载文件:
```powershell
s3cmd get s3://my-livestream-dvr/dvr/live/livestream/file.flv
```

### 使用 AWS CLI

```powershell
aws configure set aws_access_key_id YOUR_ACCESS_KEY
aws configure set aws_secret_access_key YOUR_SECRET_KEY

aws s3 ls s3://my-livestream-dvr/dvr/ --endpoint-url=https://sgp1.digitaloceanspaces.com
```

## 参考资料

- [DigitalOcean Spaces 文档](https://docs.digitalocean.com/products/spaces/)
- [Spaces API 参考](https://docs.digitalocean.com/reference/api/spaces-api/)
- [S3 兼容 API](https://docs.aws.amazon.com/AmazonS3/latest/API/Welcome.html)
