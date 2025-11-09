# 番茄小说自动上传功能测试报告

## 测试时间
2025-10-30

## 测试账号
- 手机号: 13378256469
- 密码: Qq1991751131

## 测试书籍信息
- 书名: 槐树村的娄昭君的新书
- 书籍ID: 7566232657483287576
- 默认分卷: 第一卷：默认

## 一、登录流程测试

### 1.1 登录方式
番茄小说支持两种登录方式:
- **验证码登录** (默认)
- **密码登录**

### 1.2 密码登录流程
1. 访问登录页面: `https://fanqienovel.com/main/writer/login`
2. 点击"密码登录"按钮切换到密码登录模式
3. 填写手机号/邮箱
4. 填写密码
5. 勾选用户协议复选框
6. 点击"登录"按钮
7. 登录成功后跳转到: `https://fanqienovel.com/main/writer/`

### 1.3 关键发现
✅ **密码登录可用** - 虽然有提示"为保证账号安全,请使用手机验证码登录",但实际上密码登录仍然可以成功
✅ **Cookie持久化** - 登录成功后会生成Cookie,可以保存用于后续自动化

### 1.4 重要Cookie字段
```
serial_uuid=7566646000153101860
serial_webid=7566646000153101860
passport_csrf_token=3b5f9f2955f0a31af7e71063479ba6f0
passport_csrf_token_default=3b5f9f2955f0a31af7e71063479ba6f0
novel_web_id=7566646000153101860
csrf_session_id=51921850615fe29cccfba5eff5c71358
```

## 二、章节创建与发布流程测试

### 2.1 创建章节入口
- 方式1: 工作台 -> 点击书籍卡片的"创建章节"按钮
- 方式2: 章节管理页面 -> 点击"新建章节"按钮

### 2.2 章节编辑页面结构

#### 页面URL格式
```
https://fanqienovel.com/main/writer/{book_id}/publish/{chapter_id}?enter_from=newchapter_0
```

#### 页面元素
1. **顶部信息栏**
   - 书名显示
   - 当前分卷显示
   - 保存状态显示 (保存中/已保存到云端)
   - 正文字数统计

2. **章节信息区**
   - 章节序号输入框 (textbox)
   - 章节标题输入框 (textbox, placeholder="请输入标题", 最多30字)

3. **正文编辑器**
   - 使用 **ProseMirror** 富文本编辑器
   - 元素类型: `<div class="ProseMirror" contenteditable="true">`
   - 支持段落格式化
   - 自动保存到云端

4. **工具栏**
   - AI写作
   - 人物设定
   - AI插图
   - AI起名
   - 灵感生成
   - AI查询
   - 风险提示

5. **作者有话说** (可选)
   - 不计入正文字数
   - 与章节同时发布

### 2.3 填写章节内容

#### 章节序号
- 输入框类型: textbox
- 填写方式: 直接输入数字,如 "1"

#### 章节标题
- 输入框类型: textbox
- 字数限制: 最多30字
- 填写方式: 直接输入文本

#### 正文内容
- 编辑器类型: ProseMirror (contenteditable div)
- **最低字数要求: 1000字**
- 填写方式:
  ```javascript
  const editor = document.querySelector('.ProseMirror');
  editor.innerHTML = '<p>段落内容</p>';
  editor.dispatchEvent(new Event('input', { bubbles: true }));
  ```

### 2.4 内容要求
- ✅ 正文至少1000字
- ✅ 需要是正常的小说内容,不能是测试文字或无关内容
- ✅ 不能包含违规内容
- ✅ 建议使用全角空格缩进 (　　)

### 2.5 发布流程

#### 步骤1: 点击"下一步"按钮
- 触发内容保存
- 检查字数是否满足要求
- 如果字数不足,会提示"正文至少输入1000字"

#### 步骤2: 内容风险检测
- 弹窗询问"是否进行内容风险检测?"
- 选项: 取消 / 确定
- 建议选择"确定"进行检测
- 检测结果: "检测暂无风险,可发布或继续修改"

#### 步骤3: 发布设置
弹出"发布设置"对话框,包含以下选项:

1. **分卷选择**
   - 显示当前分卷: "第一卷：默认"
   - 可以选择其他分卷

2. **章节确认**
   - 显示章节信息: "第1章 初遇仙缘"

3. **是否使用AI** (必选)
   - 选项: 是 / 否
   - **必须选择一个选项,否则无法发布**

4. **定时发布** (可选)
   - 开关按钮
   - 关闭时: 章节在通过审核后会立即发布
   - 开启时: 可以设置发布时间

#### 步骤4: 确认发布
- 点击"确认发布"按钮
- 提交成功后显示: "已提交,预计1小时内完成审核"
- 自动跳转到章节管理页面

### 2.6 发布后状态
章节管理页面显示:
- 章节名称: 第1章 初遇仙缘
- 字数: - (审核中未显示)
- 错别字: 0
- 审核状态: **审核中**
- 发布时间: 2025-10-30 18:32

## 三、关键技术发现

### 3.1 编辑器操作
```javascript
// 查找编辑器
const editor = document.querySelector('.ProseMirror');

// 填写内容
editor.innerHTML = '<p>段落1</p><p>段落2</p>';

// 触发保存
editor.dispatchEvent(new Event('input', { bubbles: true }));

// 获取字数
const text = editor.innerText;
const wordCount = text.length;
```

### 3.2 页面元素选择器

#### 登录页面
- 密码登录按钮: `button` 包含文本 "密码登录"
- 手机号输入框: `input[type="text"]` 第一个
- 密码输入框: `input[type="password"]`
- 用户协议复选框: `input[type="checkbox"]`
- 登录按钮: `button` 包含文本 "登录"

#### 编辑页面
- 章节序号输入框: `input[type="text"]` (在"第"和"章"之间)
- 章节标题输入框: `input[placeholder="请输入标题"]`
- 正文编辑器: `.ProseMirror` (第一个)
- 下一步按钮: `button` 包含文本 "下一步"

#### 发布设置对话框
- AI使用选项-否: `label` 包含文本 "否"
- 确认发布按钮: `button` 包含文本 "确认发布"

### 3.3 自动保存机制
- 编辑器内容变化后会自动保存到云端
- 保存状态显示: "保存中" -> "已保存到云端"
- 建议在点击"下一步"前等待保存完成

## 四、现有代码问题分析

### 4.1 `fanqie_publisher_service.py` 需要修正的地方

#### 问题1: 登录流程
现有代码可能没有正确处理密码登录流程,需要确认:
- 是否正确切换到密码登录模式
- 是否正确勾选用户协议
- 是否正确处理登录后的跳转

#### 问题2: 编辑器操作
需要确认:
- 是否使用正确的选择器定位ProseMirror编辑器
- 是否正确触发input事件以保存内容
- 是否等待保存完成

#### 问题3: 发布设置
需要确认:
- 是否正确选择"是否使用AI"选项
- 是否处理定时发布设置

#### 问题4: 字数检查
需要添加:
- 发布前检查字数是否满足1000字要求
- 如果不足,给出明确提示

## 五、测试结论

### 5.1 成功验证的功能
✅ 密码登录可用
✅ Cookie可以持久化
✅ 章节创建流程完整
✅ ProseMirror编辑器可以通过JavaScript操作
✅ 内容风险检测可用
✅ 发布流程完整
✅ 章节提交成功

### 5.2 需要注意的要点
⚠️ 正文必须至少1000字
⚠️ 必须选择"是否使用AI"选项
⚠️ 内容必须是正常的小说内容
⚠️ 需要等待自动保存完成
⚠️ 发布后需要等待审核(约1小时)

### 5.3 下一步测试计划
1. 测试修改分卷名称
2. 测试创建第二章
3. 测试创建新分卷
4. 测试批量发布
5. 验证并修正现有代码

## 六、建议的代码修正

### 6.1 登录函数修正
```python
async def login(self, phone: str, password: str):
    """使用密码登录"""
    # 1. 访问登录页面
    await self.page.goto("https://fanqienovel.com/main/writer/login")
    await self.page.wait_for_load_state("networkidle")
    
    # 2. 切换到密码登录
    await self.page.click('button:has-text("密码登录")')
    await asyncio.sleep(1)
    
    # 3. 填写手机号
    await self.page.fill('input[type="text"]', phone)
    
    # 4. 填写密码
    await self.page.fill('input[type="password"]', password)
    
    # 5. 勾选用户协议
    await self.page.click('input[type="checkbox"]')
    
    # 6. 点击登录
    await self.page.click('button:has-text("登录")')
    
    # 7. 等待跳转
    await self.page.wait_for_url("**/main/writer/**")
    
    return True
```

### 6.2 发布章节函数修正
```python
async def publish_chapter(self, book_id: str, chapter_number: int, title: str, content: str):
    """发布章节"""
    # 1. 检查字数
    if len(content) < 1000:
        raise ValueError(f"章节内容不足1000字,当前{len(content)}字")
    
    # 2. 访问创建章节页面
    url = f"https://fanqienovel.com/main/writer/{book_id}/publish/?enter_from=newchapter"
    await self.page.goto(url)
    await self.page.wait_for_load_state("networkidle")
    
    # 3. 关闭引导弹窗(如果有)
    # ... 省略
    
    # 4. 填写章节序号
    await self.page.fill('input[type="text"]', str(chapter_number))
    
    # 5. 填写章节标题
    await self.page.fill('input[placeholder="请输入标题"]', title)
    
    # 6. 填写正文内容
    await self.page.evaluate(f'''() => {{
        const editor = document.querySelector('.ProseMirror');
        editor.innerHTML = `{content}`;
        editor.dispatchEvent(new Event('input', {{ bubbles: true }}));
    }}''')
    
    # 7. 等待保存完成
    await self.page.wait_for_selector('text=已保存到云端')
    
    # 8. 点击下一步
    await self.page.click('button:has-text("下一步")')
    
    # 9. 风险检测
    await self.page.click('button:has-text("确定")')
    await self.page.wait_for_selector('text=检测暂无风险')
    
    # 10. 发布设置
    await self.page.click('label:has-text("否")')  # 选择不使用AI
    await self.page.click('button:has-text("确认发布")')
    
    # 11. 等待提交成功
    await self.page.wait_for_selector('text=已提交')
    
    return True
```

## 七、附录

### 7.1 测试用的小说内容示例
```
第一章 初遇仙缘

　　清晨的阳光透过窗棂,洒在青石板铺就的小院里。
　　李云从床上坐起,揉了揉惺忪的睡眼。昨夜做了一个奇怪的梦...
(省略,总计1626字)
```

### 7.2 重要URL列表
- 登录页面: `https://fanqienovel.com/main/writer/login`
- 工作台: `https://fanqienovel.com/main/writer/`
- 章节管理: `https://fanqienovel.com/main/writer/chapter-manage/{book_id}&{book_name}?type=1`
- 创建章节: `https://fanqienovel.com/main/writer/{book_id}/publish/?enter_from=newchapter`
- 编辑章节: `https://fanqienovel.com/main/writer/{book_id}/publish/{chapter_id}?enter_from=newchapter_0`

