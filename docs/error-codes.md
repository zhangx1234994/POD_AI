# 错误码文档

## 1. 错误码格式

错误码采用 `模块_三位数字` 的格式，例如：`AUTH_001`

- **模块**：标识错误所属的功能模块
- **三位数字**：具体错误类型，从001开始递增

## 2. 模块标识

| 模块标识 | 模块名称 | 说明 |
|---------|---------|------|
| COMMON  | 通用错误 | 适用于多个模块的通用错误 |
| AUTH    | 认证相关 | 登录、授权等认证相关错误 |
| USER    | 用户相关 | 用户管理相关错误 |
| REGISTER | 注册相关 | 用户注册相关错误 |
| ABILITY | 能力/执行器 | 统一能力 API、AbilityTask、执行节点、ComfyUI 队列等相关错误 |
| SYSTEM  | 系统错误 | 系统级错误 |

## 3. 错误码列表

### 3.1 通用错误 (COMMON)

| 错误码 | 错误信息 | HTTP状态码 | 说明 |
|-------|---------|-----------|------|
| COMMON_001 | 请求参数错误 | 400 | 请求参数不合法或缺失 |
| COMMON_002 | 服务器内部错误 | 500 | 服务器处理请求时发生内部错误 |
| COMMON_003 | 资源不存在 | 404 | 请求的资源不存在 |

### 3.2 认证相关错误 (AUTH)

| 错误码 | 错误信息 | HTTP状态码 | 说明 |
|-------|---------|-----------|------|
| AUTH_001 | 用户名或密码错误 | 401 | 用户名或密码不正确 |
| AUTH_002 | 未授权访问 | 401 | 缺少有效的认证信息 |
| AUTH_003 | 登录信息已过期，请重新登录 | 401 | 认证信息已过期 |
| AUTH_004 | 登录失败次数过多，请稍后重试 | 429 | 登录失败次数超过限制 |

### 3.3 用户相关错误 (USER)

| 错误码 | 错误信息 | HTTP状态码 | 说明 |
|-------|---------|-----------|------|
| USER_001 | 用户名不能为空 | 400 | 用户名为空 |
| USER_002 | 密码不能为空 | 400 | 密码为空 |
| USER_003 | 邮箱不能为空 | 400 | 邮箱为空 |
| USER_004 | 用户名已存在 | 409 | 用户名已被注册 |
| USER_005 | 邮箱已存在 | 409 | 邮箱已被注册 |
| USER_006 | 手机号已存在 | 409 | 手机号已被注册 |
| USER_007 | 用户不存在 | 404 | 用户不存在 |
| USER_008 | 当前密码不正确 | 400 | 输入的当前密码不正确 |
| USER_009 | 新密码不能为空 | 400 | 新密码为空 |
| USER_010 | 昵称不能为空 | 400 | 昵称为空 |

### 3.4 注册相关错误 (REGISTER)

| 错误码 | 错误信息 | HTTP状态码 | 说明 |
|-------|---------|-----------|------|
| REGISTER_001 | 注册失败，请稍后重试 | 500 | 注册过程中发生错误 |
| REGISTER_002 | 用户名已存在 | 409 | 用户名已被注册 |
| REGISTER_003 | 邮箱已存在 | 409 | 邮箱已被注册 |
| REGISTER_004 | 手机号已存在 | 409 | 手机号已被注册 |
| REGISTER_005 | 用户名长度不能小于6个字符 | 400 | 用户名长度不足 |
| REGISTER_006 | 密码长度不能小于6个字符 | 400 | 密码长度不足 |
| REGISTER_007 | 邮箱格式不正确 | 400 | 邮箱格式不符合规范 |
| REGISTER_008 | 手机号格式不正确 | 400 | 手机号格式不符合规范 |

### 3.5 系统错误 (SYSTEM)

| 错误码 | 错误信息 | HTTP状态码 | 说明 |
|-------|---------|-----------|------|
| SYSTEM_001 | 系统维护中，请稍后重试 | 503 | 系统正在维护 |
| SYSTEM_002 | 服务暂时不可用，请稍后重试 | 503 | 服务暂时无法处理请求 |

### 3.6 能力/执行器相关错误 (ABILITY)

> 所有原子能力、AbilityTask、执行节点、ComfyUI 工作流都归类到该模块。管理端“统一能力接口”与客户端调用 `/api/abilities`、`/api/ability-tasks` 时需重点关注这些错误，并向用户展示可操作的提示。

| 错误码 | 错误信息 | HTTP状态码 | 说明 |
|-------|---------|-----------|------|
| ABILITY_001 | 能力未绑定可用执行节点 | 400 | 数据库中缺少 `executor_id` 或节点处于禁用状态。 |
| ABILITY_002 | 能力已停用或不存在 | 404 | `ability_id` 不存在或 `status != active`。 |
| ABILITY_003 | 能力类型暂不支持该操作 | 400 | 请求方式与能力类型不兼容，如在非 ComfyUI 能力上传 LoRA。 |
| ABILITY_004 | 输入参数不合法 | 400 | `input_schema` 校验失败，常见于缺少图片/必填字段。 |
| ABILITY_005 | AbilityTask 不存在或无权访问 | 404 | 查询的任务 ID 无效或属于其他用户。 |
| ABILITY_006 | AbilityTask 正在排队，请稍后重试 | 429 | 超出 `ABILITY_TASK_MAX_WORKERS` 或单节点 `max_concurrency`。 |
| ABILITY_007 | 执行节点不可达，请检查网络/鉴权 | 502 | 访问 Baidu/Volcengine/KIE/ComfyUI 失败（网络、凭证、超时）。 |
| ABILITY_008 | 第三方 API 返回错误 | 502 | 厂商接口返回非 2xx，`details` 中附带原始错误码。 |
| ABILITY_009 | 媒资上传失败，请重试 | 500 | 能力执行成功但 OSS 落地失败，结果未能提供下载链接。 |
| ABILITY_010 | ComfyUI 队列异常 | 503 | `/queue/status` 返回 `COMFYUI_QUEUE_STATUS_ERROR` 或节点挂掉。 |
| ABILITY_011 | 能力成本配置缺失 | 500 | `metadata.pricing` 未配置且缺省成本失效，无法写入日志。 |

## 4. 错误响应格式

### 4.1 成功响应
```json
{
  "user_id": "123456",
  "username": "testuser",
  "nickname": "测试用户",
  "email": "test@example.com",
  "mobile": "13800138000",
  "platform": 1
}
```

### 4.2 错误响应
```json
{
  "code": "REGISTER_002",
  "message": "用户名已存在",
  "details": null,
  "timestamp": 1635789012345
}
```

## 5. 错误码使用示例

### 5.1 后端使用示例

```java
// 用户名已存在错误
if (userMapper.existsByUsername(username)) {
    throw new IllegalStateException("用户名已存在");
}

// 或直接返回错误响应
return ResponseEntity.status(409)
        .body(ApiErrorResponse.error(ErrorCode.REGISTER_002.getCode(), ErrorCode.REGISTER_002.getMessage()));

// 能力未绑定执行节点
if (!ability.hasExecutor()) {
    throw new ApiException(ErrorCode.ABILITY_001);
}
```

### 5.2 前端使用示例

```typescript
// 登录请求
async function login(username: string, password: string) {
  try {
    const response = await authHttp.post('/login', { username, password });
    return response.data;
  } catch (error: any) {
    // 使用友好错误信息
    const errorMessage = error?.friendlyMessage || '登录失败';
    setError(errorMessage);
    throw error;
  }
}

// 统一能力接口
async function invokeAbility(abilityId: string, payload: AbilityInvokePayload) {
  try {
    const { data } = await http.post(`/api/abilities/${abilityId}/invoke`, payload);
    return data;
  } catch (error: any) {
    if (error?.response?.data?.code === 'ABILITY_001') {
      toast.error('请先在管理端绑定执行节点');
    } else if (error?.response?.data?.code === 'ABILITY_006') {
      toast.warn('任务排队中，请稍后重试');
    } else {
      toast.error('能力调用失败，请稍后再试');
    }
    throw error;
  }
}
```

## 6. 最佳实践

1. **错误码一致性**：前后端必须使用相同的错误码体系
2. **友好提示**：错误信息应简洁明了，便于用户理解
3. **详细日志**：后端应记录详细的错误日志，便于问题排查
4. **错误码维护**：定期更新错误码文档，确保与代码一致
5. **国际化支持**：考虑支持多语言错误提示

## 7. 错误码管理

- 新增错误码：在 `ErrorCode.java` 和 `ERROR_MESSAGES` 中同时添加
- 修改错误码：确保前后端同步修改
- 废弃错误码：标记为废弃，逐步替换为新错误码
- 定期审查：定期审查错误码使用情况，优化错误处理逻辑

## 8. 常见问题

### 8.1 如何添加新的错误码？

1. 在 `ErrorCode.java` 中添加新的枚举值
2. 在 `ERROR_MESSAGES` 中添加对应的映射
3. 更新错误码文档
4. 确保前后端使用一致

### 8.2 如何处理未定义的错误码？

前端应设置默认错误提示，如 "请求失败，请稍后重试"，避免显示原始错误码

### 8.3 如何优化错误提示？

- 使用用户友好的语言
- 提供明确的解决方案
- 根据错误类型选择合适的提示方式（弹窗、Toast、页面内提示等）

## 9. 版本历史

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| v1.0 | 2025-12-11 | 初始版本，包含基础错误码 |
| v1.1 | 2025-12-11 | 细化注册相关错误码，增加更多场景 |
| v1.2 | 2026-01-15 | 新增 ABILITY 模块错误码，覆盖统一能力 API/AbilityTask/ComfyUI 队列 |

---

**备注**：本文档将定期更新，确保与最新的代码实现保持一致。
