# 上游仓库差异分析：full_content 相关改动

## 📊 对比总结

本地 novelnew 项目相对于上游 arboris-novel 项目，在 full_content 处理上新增了大量**格式检测**和**Markdown清理**功能。

**关键发现：**
- ✅ 上游项目：**不清理Markdown**，只做基础的JSON/字符串规范化
- ❌ 本地项目：**过度清理Markdown**，导致语义偏离

---

## 🔍 详细差异对比

### 1. 新增函数（本地独有）

#### 1.1 `_strip_markdown_formatting()` - Markdown清理
**位置：** `backend/app/services/ai_orchestrator_helper.py:89-135`

**功能：** 移除所有Markdown格式标记（标题、粗体、斜体、代码、链接等）

**上游状态：** ❌ **不存在**

**影响范围：**
- 被 `_clean_full_content()` 调用
- 直接修改章节内容，导致丢失格式信息

**相关提交：**
```
a1aa176 添加Markdown标记自动清理功能
ba336d4 改为无条件清理Markdown避免漏检
8d52bb9 补充content字段Markdown清理
```

---

#### 1.2 `_detect_planner_format()` - Planner格式检测
**位置：** `backend/app/services/ai_orchestrator_helper.py:138-190`

**功能：** 检测内容是否包含Planner格式的关键词（analysis、plan、queries_summary等）

**上游状态：** ❌ **不存在**

**检测模式：**
- 基础格式: `analysis:`、`"analysis":`
- Markdown粗体: `**analysis**`、`__analysis__`
- Markdown标题: `# analysis`、`## analysis`
- 阈值：检测到 ≥2 个关键词才判定为Planner格式

**影响范围：**
- `auto_generator_service.py:990` - 保存前最终验证
- `auto_generator_service.py:1052` - content字段验证
- `ai_orchestrator_helper.py:273-286` - 嵌套JSON验证

**相关提交：**
```
b77228d fix: 全面增强3Agent模式的Planner格式检测
35129bc fix: 修复Planner内容被错误保存为章节正文的严重BUG
f159e5c Refactor: Improve planner format detection logic
85e8a39 🔒 防止 Planner 格式内容被错误保存
```

---

#### 1.3 `_clean_full_content()` - full_content清理主函数
**位置：** `backend/app/services/ai_orchestrator_helper.py:238-324`

**功能：** 4层清理流程
1. 移除 `<think>` 标签和 Markdown 代码块
2. 检测嵌套JSON（包含Planner格式检测）
3. 双重转义修复（`\\n` → `\n`）
4. **Markdown标记清理**（⚠️ 问题所在）

**上游状态：** ❌ **不存在**

**上游对应实现：**
```python
# 上游 novel_service.py 的 _clean_string()
def _clean_string(text: str) -> str:
    """仅处理转义字符，不清理Markdown"""
    text = text.strip()
    # 处理JSON转义（如 \\n、\\t）
    if text.startswith('"') and text.endswith('"'):
        try:
            text = json.loads(text)
        except json.JSONDecodeError:
            pass
    return text
```

**关键差异：**
| 步骤 | 上游 arboris-novel | 本地 novelnew |
|------|-------------------|---------------|
| think标签移除 | ❌ 无 | ✅ 有 |
| Markdown代码块提取 | ❌ 无 | ✅ 有 |
| Planner格式检测 | ❌ 无 | ✅ 有（4层防御） |
| 双重转义修复 | ✅ 有（简单） | ✅ 有（完整） |
| **Markdown清理** | ❌ **不清理** | ❌ **过度清理** |

**相关提交：**
```
4c3d046 修复3agent模式full_content未清理的问题
45e0175 修复full_content提取失败时的降级策略
015b530 修复 Planner 格式问题的根本原因
```

---

#### 1.4 `_validate_planner_output()` - Planner输出验证
**位置：** `backend/app/services/ai_orchestrator_helper.py:193-235`

**功能：** 验证Planner不返回Writer专属字段（full_content、content、chapter_content）

**上游状态：** ❌ **不存在**

---

### 2. 修改的函数（与上游不同）

#### 2.1 `auto_generator_service.py` 中的 full_content 处理

**新增检测点：**

##### 检测点1：嵌套JSON + Planner格式检测
**位置：** `auto_generator_service.py:924-934`
```python
# ✅ 防御性处理：检查full_content是否被错误地嵌套成JSON字符串
if isinstance(full_content, str) and full_content.strip().startswith("{"):
    try:
        nested = json.loads(full_content)
        if isinstance(nested, dict) and "full_content" in nested:
            logger.warning(f"检测到嵌套JSON，自动提取")
            full_content = nested["full_content"]
    except json.JSONDecodeError:
        pass
```

##### 检测点2：Planner关键词检测
**位置：** `auto_generator_service.py:936-989`
```python
# ✅ 检测Planner格式：防止错误地保存Planner的分析结果
if isinstance(full_content, str):
    content_stripped = full_content.strip()
    if content_stripped.startswith("{") and content_stripped.endswith("}"):
        try:
            parsed = json.loads(content_stripped)
            if isinstance(parsed, dict):
                # 检测Planner关键词
                planner_keywords = ["analysis", "plan", "queries_summary", "notes_for_writer"]
                found_planner = [k for k in planner_keywords if k in parsed]

                if found_planner and "full_content" not in parsed:
                    raise ValueError("检测到Planner格式，拒绝保存")
```

##### 检测点3：非JSON内容的关键词检测
**位置：** `auto_generator_service.py:937-989`
```python
# 非JSON响应的关键词检测
is_planner, count, matched = _detect_planner_format(full_content, check_length=1000)
if is_planner:
    logger.error(f"检测到Planner格式关键词: {matched}")
    # 根据轮数决定重试或抛异常
```

##### 检测点4：保存前最终验证
**位置：** `auto_generator_service.py:990-1002`
```python
# ========== 最终验证：保存前检测Planner格式（最后一道防线） ==========
is_planner_final, count_final, matched_final = _detect_planner_format(full_content)
if is_planner_final:
    logger.critical(f"保存前检测到Planner格式内容！")
    raise ValueError("拒绝保存Planner格式的内容")
```

**上游状态：** ❌ **完全不存在这些检测**

---

### 3. 前端相关

#### 3.1 ChapterContent.vue 中的使用

**需要检查的位置：**
```bash
frontend/src/components/ChapterContent.vue
- cleanVersionContent() 函数
- exportChapterAsTxt() 函数
- 任何显示/复制章节内容的地方
```

**预期问题：**
- 前端可能依赖后端已经清理过的 full_content
- 导出TXT时可能需要纯文本，但现在后端已经清理了

---

## 🎯 改造方案

### 目标
将 full_content 的语义恢复为上游标准：
- **后端：** 保留 Markdown 格式，只做结构清洗
- **前端：** 需要纯文本时本地清洗

---

### TODO 2: 后端修改

#### 修改1: `_clean_full_content()` - 移除Markdown清理步骤

**文件：** `backend/app/services/ai_orchestrator_helper.py:238-324`

**现状（错误）：**
```python
def _clean_full_content(content: str, chapter_number: int = 0, version_idx: int = 0) -> str:
    # 步骤0: 移除 think 标签 ✅ 保留
    content = remove_think_tags(content)
    content = unwrap_markdown_json(content)

    # 步骤1: 检测嵌套JSON ✅ 保留（包含Planner检测）
    if content.strip().startswith("{"):
        # Planner格式检测逻辑 ✅ 保留
        ...

    # 步骤2: 双重转义修复 ✅ 保留
    content = content.replace("\\n", "\n")
    ...

    # 步骤3: Markdown标记清理 ❌ 移除
    cleaned = _strip_markdown_formatting(content)  # <-- 删除这步
    return cleaned
```

**修改为（正确）：**
```python
def _clean_full_content(content: str, chapter_number: int = 0, version_idx: int = 0) -> str:
    # 步骤0: 移除 think 标签 ✅ 保留
    content = remove_think_tags(content)
    content = unwrap_markdown_json(content)

    # 步骤1: 检测嵌套JSON ✅ 保留（包含Planner检测）
    if content.strip().startswith("{"):
        # Planner格式检测逻辑 ✅ 保留
        ...

    # 步骤2: 双重转义修复 ✅ 保留
    content = content.replace("\\n", "\n")
    ...

    # ❌ 移除步骤3：不再清理Markdown
    return content  # 直接返回，保留Markdown格式
```

---

#### 修改2: `_strip_markdown_formatting()` - 标记为仅用于检测

**文件：** `backend/app/services/ai_orchestrator_helper.py:89-135`

**选项A（保守）：** 保留函数，但改名和注释说明仅用于检测
```python
def _strip_markdown_formatting_for_detection_only(text: str) -> str:
    """
    ⚠️ 仅用于格式检测，不应用于实际内容清洗！

    移除Markdown格式标记用于检测Planner格式关键词。
    实际保存的full_content应该保留Markdown格式。
    """
    # ... 保持逻辑不变
```

**选项B（激进）：** 完全删除函数
- 风险：可能有其他地方在使用
- 需要先全局搜索引用

**推荐：** 选项A（保守方案）

---

#### 修改3: Planner检测逻辑 - 保留但优化

**文件：** `backend/app/services/ai_orchestrator_helper.py:138-190`

**现状：** ✅ 功能正确，无需修改

**说明：**
- Planner格式检测是合理的防御机制
- 检测逻辑不影响内容格式
- 应该保留所有4层防御

---

### TODO 3: 前端修改

#### 修改1: 添加本地Markdown清理函数

**文件：** `frontend/src/components/ChapterContent.vue`

**新增函数：**
```javascript
// 前端本地清理Markdown（用于导出/复制纯文本）
function stripMarkdownFormatting(text) {
  if (!text) return text;

  // 移除标题标记
  text = text.replace(/^#{1,6}\s+/gm, '');

  // 移除粗体 **text** 或 __text__
  text = text.replace(/\*\*(.+?)\*\*/g, '$1');
  text = text.replace(/__(.+?)__/g, '$1');

  // 移除斜体 *text* 或 _text_
  text = text.replace(/\*(.+?)\*/g, '$1');
  text = text.replace(/(?<!\w)_(.+?)_(?!\w)/g, '$1');

  // 移除行内代码 `code`
  text = text.replace(/`(.+?)`/g, '$1');

  // 移除链接 [text](url) -> text
  text = text.replace(/\[(.+?)\]\(.+?\)/g, '$1');

  // 移除图片 ![alt](url) -> alt
  text = text.replace(/!\[(.+?)\]\(.+?\)/g, '$1');

  // 移除引用标记 >
  text = text.replace(/^>\s+/gm, '');

  // 移除列表标记
  text = text.replace(/^[\*\-\+]\s+/gm, '');
  text = text.replace(/^\d+\.\s+/gm, '');

  // 移除Markdown硬换行
  text = text.replace(/\\\s*\n/g, '\n');

  return text;
}
```

#### 修改2: 更新导出/复制功能

**原来（错误 - 依赖后端清理）：**
```javascript
function exportChapterAsTxt() {
  // 直接使用 full_content（后端已清理）
  const content = chapter.content;
  downloadAsTxt(content);
}
```

**修改为（正确 - 前端本地清理）：**
```javascript
function exportChapterAsTxt() {
  // 从后端获取带Markdown的内容，前端清理
  const rawContent = chapter.content;
  const cleanedContent = stripMarkdownFormatting(rawContent);
  downloadAsTxt(cleanedContent);
}
```

#### 修改3: 更新复制功能

**类似的修改应用于：**
- `copyChapterContent()` - 复制为纯文本
- `cleanVersionContent()` - 如果用于显示纯文本预览

---

## 📝 保留的功能（不修改）

### ✅ 应该保留的检测逻辑

1. **`_detect_planner_format()`** - Planner格式检测（核心防御）
2. **`_validate_planner_output()`** - Planner输出验证
3. **`remove_think_tags()`** - think标签移除
4. **`unwrap_markdown_json()`** - Markdown代码块提取
5. **`sanitize_json_like_text()`** - JSON清洗
6. **双重转义修复** - `\\n` → `\n` 转换
7. **嵌套JSON检测** - 防止JSON字符串嵌套
8. **4层Planner格式防御** - auto_generator_service.py中的检测点

**原因：** 这些是针对AI模型输出异常的防御机制，与内容格式无关

---

## 🔧 实施步骤

### 步骤1: 后端修改
```bash
1. 修改 ai_orchestrator_helper.py:_clean_full_content()
   - 移除步骤3（Markdown清理）
   - 直接返回内容，保留Markdown

2. 重命名 _strip_markdown_formatting()
   - 改为 _strip_markdown_formatting_for_detection_only()
   - 添加警告注释

3. 验证所有调用点
   - 确保没有其他地方调用 _strip_markdown_formatting()
```

### 步骤2: 前端修改
```bash
1. 添加 stripMarkdownFormatting() 函数到 ChapterContent.vue

2. 更新以下函数调用清理逻辑：
   - exportChapterAsTxt()
   - copyChapterContent()
   - cleanVersionContent()（如果用于纯文本）

3. 保留显示内容的Markdown渲染
   - 使用 marked.js 或其他Markdown渲染器
   - 或者保持原样（如果前端不渲染Markdown）
```

### 步骤3: 测试验证
```bash
1. 测试3Agent模式生成章节
   - 验证保存的full_content包含Markdown
   - 验证Planner格式检测仍然生效

2. 测试前端导出TXT
   - 验证导出的TXT是纯文本（无Markdown）

3. 测试前端复制功能
   - 验证复制的内容是纯文本（无Markdown）

4. 测试显示功能
   - 验证章节显示正常（带或不带Markdown渲染）
```

---

## 📚 相关提交历史

```bash
# Planner格式检测相关（✅ 保留）
b77228d fix: 全面增强3Agent模式的Planner格式检测
35129bc fix: 修复Planner内容被错误保存为章节正文的严重BUG
f159e5c Refactor: Improve planner format detection logic
85e8a39 🔒 防止 Planner 格式内容被错误保存

# Markdown清理相关（❌ 需要移除）
a1aa176 添加Markdown标记自动清理功能
ba336d4 改为无条件清理Markdown避免漏检
8d52bb9 补充content字段Markdown清理
065aba2 禁止3Agent Writer使用Markdown标记

# full_content清理相关（⚠️ 需要修改）
4c3d046 修复3agent模式full_content未清理的问题
45e0175 修复full_content提取失败时的降级策略
015b530 修复 Planner 格式问题的根本原因
```

---

## ✅ 总结

### 主要问题
本地项目在修复"Planner格式误保存"问题时，过度引入了Markdown清理逻辑，导致：
1. full_content 丢失格式信息
2. 与上游语义不一致
3. 前端可能依赖后端清理（不符合职责分离）

### 正确方向
- **后端：** 只负责结构清洗（JSON提取、转义修复、Planner检测）
- **前端：** 需要纯文本时自行清洗Markdown
- **保留：** 所有Planner格式检测逻辑（防御机制）

### 影响范围
- ✅ 小：主要集中在2个文件（ai_orchestrator_helper.py、auto_generator_service.py）
- ✅ 可逆：修改简单，风险可控
- ⚠️ 需要测试：确保前端功能正常
