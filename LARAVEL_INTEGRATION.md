# Laravel 集成指南

使用 Webhook 方式，上传完成后自动调用你的 Laravel API。

## Laravel 端设置

### 1. 创建 API Route

编辑 `routes/api.php`:

```php
Route::post('/dvr/upload-complete', [DvrController::class, 'uploadComplete']);
```

### 2. 创建 Controller

```bash
php artisan make:controller Api/DvrController
```

编辑 `app/Http/Controllers/Api/DvrController.php`:

```php
<?php

namespace App\Http\Controllers\Api;

use App\Http\Controllers\Controller;
use Illuminate\Http\Request;
use App\Models\DvrRecording;
use Illuminate\Support\Facades\Log;

class DvrController extends Controller
{
    public function uploadComplete(Request $request)
    {
        // 验证 webhook secret
        $secret = config('services.dvr.webhook_secret');
        if ($secret && $request->header('X-Webhook-Secret') !== $secret) {
            return response()->json(['error' => 'Unauthorized'], 401);
        }
        
        // 验证请求数据
        $validated = $request->validate([
            'filename' => 'required|string',
            'file_url' => 'required|url',
            'file_size' => 'required|integer',
            'upload_time' => 'required|string',
            'stream_app' => 'required|string',
            'stream_name' => 'required|string',
            'timestamp' => 'required|string',
            'bucket' => 'nullable|string',
            'region' => 'nullable|string',
        ]);
        
        // 保存到数据库
        try {
            $recording = DvrRecording::create([
                'filename' => $validated['filename'],
                'file_url' => $validated['file_url'],
                'file_size' => $validated['file_size'],
                'upload_time' => $validated['upload_time'],
                'stream_app' => $validated['stream_app'],
                'stream_name' => $validated['stream_name'],
                'timestamp' => $validated['timestamp'],
                'bucket' => $validated['bucket'] ?? null,
                'region' => $validated['region'] ?? null,
            ]);
            
            Log::info('DVR recording saved', ['id' => $recording->id, 'filename' => $recording->filename]);
            
            return response()->json([
                'success' => true,
                'id' => $recording->id,
                'message' => 'Recording saved successfully'
            ], 200);
            
        } catch (\Exception $e) {
            Log::error('Failed to save DVR recording', ['error' => $e->getMessage()]);
            
            return response()->json([
                'success' => false,
                'error' => 'Failed to save recording'
            ], 500);
        }
    }
}
```

### 3. 创建 Model

```bash
php artisan make:model DvrRecording -m
```

编辑 migration 文件 `database/migrations/xxxx_create_dvr_recordings_table.php`:

```php
<?php

use Illuminate\Database\Migrations\Migration;
use Illuminate\Database\Schema\Blueprint;
use Illuminate\Support\Facades\Schema;

return new class extends Migration
{
    public function up(): void
    {
        Schema::create('dvr_recordings', function (Blueprint $table) {
            $table->id();
            $table->string('filename');
            $table->string('file_url', 512);
            $table->bigInteger('file_size');
            $table->timestamp('upload_time');
            $table->string('stream_app', 100);
            $table->string('stream_name');
            $table->string('timestamp', 50);
            $table->string('bucket')->nullable();
            $table->string('region')->nullable();
            $table->timestamps();
            
            $table->index('stream_name');
            $table->index('upload_time');
            $table->index('timestamp');
        });
    }

    public function down(): void
    {
        Schema::dropIfExists('dvr_recordings');
    }
};
```

编辑 `app/Models/DvrRecording.php`:

```php
<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class DvrRecording extends Model
{
    protected $fillable = [
        'filename',
        'file_url',
        'file_size',
        'upload_time',
        'stream_app',
        'stream_name',
        'timestamp',
        'bucket',
        'region',
    ];

    protected $casts = [
        'upload_time' => 'datetime',
        'file_size' => 'integer',
    ];
}
```

### 4. 运行 Migration

```bash
php artisan migrate
```

### 5. 配置环境变量

编辑 `.env`:

```env
DVR_WEBHOOK_SECRET=your-secret-key-here
```

编辑 `config/services.php`:

```php
return [
    // ... 其他配置
    
    'dvr' => [
        'webhook_secret' => env('DVR_WEBHOOK_SECRET'),
    ],
];
```

## RTMP Server 端设置

### 1. 配置 .env 文件

编辑 `rtmp-server/.env`:

```env
WEBHOOK_ENABLED=true
WEBHOOK_URL=http://your-laravel-app.com/api/dvr/upload-complete
WEBHOOK_SECRET=your-secret-key-here
```

### 2. 重启服务

```powershell
docker-compose down
docker-compose up -d
```

## 测试

### 1. 推流测试

开始推流后停止，等待文件上传。

### 2. 查看日志

```powershell
# RTMP Server 日志
docker logs dvr-uploader -f

# Laravel 日志
tail -f storage/logs/laravel.log
```

### 3. 检查数据库

```php
// 在 tinker 中查看
php artisan tinker
>>> DvrRecording::latest()->first()
```

## Webhook 数据格式

POST 到你的 Laravel API 的 JSON 数据：

```json
{
    "filename": "1761221423256.flv",
    "file_url": "https://srs-tsport.sgp1.digitaloceanspaces.com/dvr/live/stream_2_68fa0d1b3a78f/1761221423256.flv",
    "file_size": 386650000,
    "upload_time": "2025-10-23T12:12:57",
    "stream_app": "live",
    "stream_name": "stream_2_68fa0d1b3a78f",
    "timestamp": "1761221423256",
    "bucket": "srs-tsport",
    "region": "sgp1"
}
```

Headers:
```
Content-Type: application/json
X-Webhook-Secret: your-secret-key-here
User-Agent: DVR-Uploader/1.0
```

## 进阶使用

### 1. 使用 Job 处理（推荐）

```php
use App\Jobs\ProcessDvrRecording;

public function uploadComplete(Request $request)
{
    // 验证 secret...
    
    ProcessDvrRecording::dispatch($request->all());
    
    return response()->json(['success' => true, 'message' => 'Queued for processing']);
}
```

创建 Job:
```bash
php artisan make:job ProcessDvrRecording
```

### 2. 添加通知

```php
use App\Notifications\DvrRecordingUploaded;
use Illuminate\Support\Facades\Notification;

// 在保存后
Notification::route('slack', config('services.slack.webhook_url'))
    ->notify(new DvrRecordingUploaded($recording));
```

### 3. 添加事件

```php
use App\Events\DvrRecordingCreated;

// 在保存后
event(new DvrRecordingCreated($recording));
```

## 故障排除

### Webhook 调用失败

1. 检查 Laravel 是否可以从 Docker 容器访问
2. 如果 Laravel 在本地，使用 `host.docker.internal`:
   ```env
   WEBHOOK_URL=http://host.docker.internal:8000/api/dvr/upload-complete
   ```

### 401 Unauthorized

检查 webhook secret 是否匹配：
- RTMP Server `.env` 中的 `WEBHOOK_SECRET`
- Laravel `.env` 中的 `DVR_WEBHOOK_SECRET`

### 422 Validation Error

检查 webhook 发送的数据格式是否正确，查看 Laravel 日志。

### 超时

如果处理时间长，考虑：
1. 先返回 200，再异步处理
2. 使用 Job Queue
3. 增加 webhook timeout（在 upload_to_spaces.py 中修改）

## API 端点示例

### 获取所有录制

```php
Route::get('/dvr/recordings', [DvrController::class, 'index']);

public function index(Request $request)
{
    $recordings = DvrRecording::query()
        ->when($request->stream_name, fn($q, $name) => $q->where('stream_name', $name))
        ->latest('upload_time')
        ->paginate(20);
    
    return response()->json($recordings);
}
```

### 删除录制

```php
Route::delete('/dvr/recordings/{id}', [DvrController::class, 'destroy']);

public function destroy(DvrRecording $recording)
{
    // 可选：同时删除 Spaces 上的文件
    // Storage::disk('spaces')->delete($recording->filename);
    
    $recording->delete();
    
    return response()->json(['success' => true]);
}
```
