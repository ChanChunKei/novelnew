# 番茄小说上传功能 - 安全性修复报告

## 修复日期
2025-10-30

## 修复概述
本次修复针对番茄小说自动上传功能的高优先级安全性问题，包括JavaScript注入风险、异常处理不当和API权限缺失等问题。

---

## 修复详情

### 1. JavaScript注入风险修复 ✅

#### 问题描述
在 `edit_volume_name` 和 `publish_chapter` 方法中，使用f-string直接拼接JavaScript代码，存在注入攻击风险。

#### 受影响的代码

**位置1：`backend/app/services/fanqie_publisher_service.py:226`**

修复前：
```python
edit_result = await self.page.evaluate(f'''() => {{
    const volumeItems = document.querySelectorAll('.chapter-volume-list-item-normal');
    for (const item of volumeItems) {{
        const nameSpan = item.querySelector('span');
        if (nameSpan && nameSpan.textContent.includes('{old_name}')) {{
            const editIcon = item.querySelector('.tomato-edit');
            if (editIcon) {{
                editIcon.click();
                return true;
            }}
        }}
    }}
    return false;
}}''')
```

修复后：
```python
edit_result = await self.page.evaluate('''(oldName) => {
    const volumeItems = document.querySelectorAll('.chapter-volume-list-item-normal');
    for (const item of volumeItems) {
        const nameSpan = item.querySelector('span');
        if (nameSpan && nameSpan.textContent.includes(oldName)) {
            const editIcon = item.querySelector('.tomato-edit');
            if (editIcon) {
                editIcon.click();
                return true;
            }
        }
    }
    return false;
}''', old_name)
```

**位置2：`backend/app/services/fanqie_publisher_service.py:407`**

修复前：
```python
await self.page.evaluate(f'''(paragraphs) => {{
    const editor = document.querySelector('.ProseMirror');
    if (editor) {{
        paragraphs.forEach(para => {{
            const p = document.createElement('p');
            p.textContent = para;
            editor.appendChild(p);
        }});
        editor.dispatchEvent(new Event('input', {{ bubbles: true }}));
    }}
}}''', paragraphs)
```

修复后：
```python
await self.page.evaluate('''(paragraphs) => {
    const editor = document.querySelector('.ProseMirror');
    if (editor) {
        paragraphs.forEach(para => {
            const p = document.createElement('p');
            p.textContent = para;
            editor.appendChild(p);
        });
        editor.dispatchEvent(new Event('input', { bubbles: true }));
    }
}''', paragraphs)
```

#### 修复方法
- 使用Playwright的参数传递机制，而不是字符串拼接
- 移除f-string，使用纯字符串模板
- 将变量作为函数参数传递给JavaScript代码

#### 安全性提升
- ✅ 防止特殊字符（单引号、反斜杠等）导致的JavaScript语法错误
- ✅ 防止恶意代码注入
- ✅ 提高代码的健壮性和可维护性

---

### 2. 异常处理改进 ✅

#### 问题描述
使用裸`except:`会捕获所有异常，包括`KeyboardInterrupt`、`SystemExit`等系统异常，可能导致程序无法正常退出。

#### 受影响的代码

**位置1：`backend/app/services/fanqie_publisher_service.py:438`**

修复前：
```python
try:
    confirm_btn = await self.page.wait_for_selector('button:has-text("确定")', timeout=3000)
    if confirm_btn:
        await confirm_btn.click()
        await asyncio.sleep(2)
except:
    logger.info("未出现风险检测对话框")
```

修复后：
```python
try:
    confirm_btn = await self.page.wait_for_selector('button:has-text("确定")', timeout=3000)
    if confirm_btn:
        await confirm_btn.click()
        await asyncio.sleep(2)
except PlaywrightTimeoutError:
    logger.info("未出现风险检测对话框")
except Exception as e:
    logger.warning(f"处理风险检测对话框时出错: {e}")
```

**位置2：`backend/app/services/fanqie_publisher_service.py:698`**

修复前：
```python
try:
    await self.page.wait_for_url("**/writer/zone/**", timeout=wait_seconds * 1000)
    logger.info("检测到登录成功")
except:
    logger.warning("未检测到登录成功，但仍会尝试保存Cookie")
```

修复后：
```python
try:
    await self.page.wait_for_url("**/writer/zone/**", timeout=wait_seconds * 1000)
    logger.info("检测到登录成功")
except PlaywrightTimeoutError:
    logger.warning("未检测到登录成功，但仍会尝试保存Cookie")
except Exception as e:
    logger.warning(f"等待登录时出错: {e}，但仍会尝试保存Cookie")
```

#### 修复方法
- 明确捕获`PlaywrightTimeoutError`异常
- 添加通用`Exception`捕获作为兜底
- 添加详细的错误日志

#### 安全性提升
- ✅ 允许系统异常正常传播，不会阻止程序退出
- ✅ 提供更详细的错误信息，便于调试
- ✅ 提高代码的可维护性

---

### 3. API权限控制 ✅

#### 问题描述
`/api/novels/fanqie/login` 接口没有权限控制，任何人都可以调用，存在被滥用的风险。

#### 受影响的代码

**位置：`backend/app/api/routers/novels.py:380`**

修复前：
```python
@router.post("/fanqie/login")
async def fanqie_manual_login(
    account: str = Body("default", description="账号标识"),
    wait_seconds: int = Body(60, description="等待登录的时间（秒）"),
) -> Dict:
    """手动登录番茄小说并保存Cookie"""
    from ...services.fanqie_publisher_service import FanqiePublisherService
    
    logger.info(f"开始番茄小说手动登录流程，账号标识: {account}")
    # ...
```

修复后：
```python
@router.post("/fanqie/login")
async def fanqie_manual_login(
    account: str = Body("default", description="账号标识"),
    wait_seconds: int = Body(60, description="等待登录的时间（秒）"),
    current_user: UserInDB = Depends(get_current_user),  # 添加权限控制
) -> Dict:
    """手动登录番茄小说并保存Cookie"""
    from ...services.fanqie_publisher_service import FanqiePublisherService
    
    logger.info(f"用户 {current_user.id} 开始番茄小说手动登录流程，账号标识: {account}")
    # ...
```

#### 修复方法
- 添加`current_user: UserInDB = Depends(get_current_user)`参数
- 在日志中记录用户ID

#### 安全性提升
- ✅ 防止未授权访问
- ✅ 防止接口被滥用
- ✅ 提供审计追踪能力

---

## 测试验证

### 1. JavaScript注入测试

测试用例：
```python
# 测试特殊字符
volume_name = "第一卷'test\"<script>alert(1)</script>"
result = await publisher.edit_volume_name("默认", volume_name)
# 预期：正常处理，不会执行恶意代码
```

### 2. 异常处理测试

测试用例：
```python
# 测试超时场景
result = await publisher.manual_login_and_save_cookies(wait_seconds=1)
# 预期：捕获PlaywrightTimeoutError，记录警告日志
```

### 3. API权限测试

测试用例：
```bash
# 未登录用户访问
curl -X POST "http://localhost:8000/api/novels/fanqie/login"
# 预期：返回401 Unauthorized

# 已登录用户访问
curl -X POST "http://localhost:8000/api/novels/fanqie/login" \
  -H "Authorization: Bearer <token>"
# 预期：正常执行
```

---

## 后续建议

### 中优先级改进（建议在下一版本实现）

1. **添加输入参数验证**
   - 验证分卷名称长度（1-20字符）
   - 验证章节标题长度（至少5字符）
   - 验证章节号为正整数

2. **改进等待策略**
   - 减少硬编码的sleep时间
   - 使用Playwright的智能等待机制
   - 提取等待时间为类常量

3. **修复资源泄漏**
   - 关闭不再使用的页面标签
   - 避免内存泄漏

### 低优先级改进（可选）

1. **代码重构**
   - 提取重复的分卷编辑逻辑
   - 改进选择器的健壮性

2. **性能优化**
   - 减少不必要的等待时间
   - 优化网络请求

---

## 提交信息

- **提交哈希**: 60714dd
- **提交时间**: 2025-10-30
- **修改文件**:
  - `backend/app/services/fanqie_publisher_service.py`
  - `backend/app/api/routers/novels.py`

---

## 总结

本次修复解决了番茄小说自动上传功能的三个高优先级安全性问题：

1. ✅ **JavaScript注入风险** - 使用参数传递代替字符串拼接
2. ✅ **异常处理不当** - 明确捕获特定异常类型
3. ✅ **API权限缺失** - 添加用户认证

这些修复显著提升了代码的安全性、健壮性和可维护性，为后续的生产环境部署奠定了基础。

