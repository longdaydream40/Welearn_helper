# WeTest HAR 抓包分析：测试页加载、保存与提交接口

> 文件来源：`wetest.sflep.com.har`  
> 目标：定位 WeLearn 测试页的试卷加载、单题保存、整卷保存/提交逻辑  
> 注意：本文档已脱敏，省略 `wlToken`、`testKey`、姓名、学号等敏感字段。

---

## 1. 结论

HAR 中测试页核心接口是：

```http
POST https://wetest.sflep.com/api/WelearnTest.aspx
```

通过 query 参数 `action` 区分具体动作：

| action | 作用 |
|---|---|
| `initTest` | 初始化测试，返回试卷 HTML、答题卡、已保存答案/播放次数、剩余时间 |
| `saveQuestion` | 保存单个题目答案或音频播放次数 |
| `savePaper` | 保存或提交整张试卷 |
| `saveLog` | 上报日志/时长；本次抓包返回 `参数错误` |

测试页面入口是：

```http
GET https://wetest.sflep.com/test/welearnTest.html?source=...&wlToken=<TOKEN>&testKey=<TEST_KEY>&backUrl=...
```

其中 `testKey` 会被前端传给 `initTest`，`wlToken` 出现在页面入口 URL 中。

---

## 2. 抓包概况

本次 HAR 共 33 条请求：

| 类型 | 数量 |
|---|---:|
| `GET` | 26 |
| `POST` | 7 |
| `200` 响应 | 31 |
| `206` 响应 | 2 |

主要域名：

| 域名 | 数量 | 用途 |
|---|---:|---|
| `wetest.sflep.com` | 14 | 测试页 HTML、CSS、JS、API |
| `wetestoss.sflep.com` | 19 | 静态资源、音频资源 |

核心 API 请求：

```text
7 x POST https://wetest.sflep.com/api/WelearnTest.aspx
```

---

## 3. 前端调用链

页面加载：

```http
GET /test/welearnTest.html?source=...&wlToken=<TOKEN>&testKey=<TEST_KEY>&backUrl=...
```

前端脚本：

```http
GET /test/script/WelearnTest.js
```

脚本中的关键逻辑：

```js
testEnv.testKey = encodeURIComponent(sp.get('testKey'));

$.ajax({
    url: "../api/WelearnTest.aspx?action=initTest&testKey=" + testEnv.testKey,
    type: "POST"
});
```

调用流程：

```text
打开 welearnTest.html
        ↓
从 URL 读取 testKey
        ↓
POST /api/WelearnTest.aspx?action=initTest&testKey=<TEST_KEY>
        ↓
返回 testId、paperContent、answerSheet、paperAnswer、remainSeconds
        ↓
用户答题/播放音频
        ↓
POST action=saveQuestion 保存单题或音频播放次数
        ↓
POST action=savePaper 保存或提交整卷
```

---

## 4. initTest：初始化测试

### 4.1 请求

```http
POST /api/WelearnTest.aspx?action=initTest&testKey=<TEST_KEY>
Host: wetest.sflep.com
```

本次抓包中该请求没有 JSON 请求体，认证/定位信息主要来自 URL 中的 `testKey` 和浏览器上下文。

### 4.2 响应结构

```json
{
  "status": 0,
  "data": {
    "testId": "<TEST_ID>",
    "isFinish": false,
    "answerSheet": "<html string>",
    "paperContent": "<html string>",
    "partNum": 1,
    "paperAnswer": {},
    "remainSeconds": 275
  }
}
```

字段说明：

| 字段 | 含义 |
|---|---|
| `testId` | 本次测试实例 ID |
| `isFinish` | 是否已完成 |
| `answerSheet` | 答题卡 HTML |
| `paperContent` | 试卷主体 HTML |
| `partNum` | 当前 Part |
| `paperAnswer` | 已保存的作答记录和音频播放次数 |
| `remainSeconds` | 剩余秒数 |

注意：`paperAnswer` 是用户当前已保存答案/状态，不是标准答案。

---

## 5. 试卷内容结构

`paperContent` 是 HTML 字符串。本次抓包里可解析出：

- 1 个 Part；
- 10 道单选题；
- 每题 4 个选项；
- 13 个音频播放入口；
- 音频资源路径位于 `wetestoss.sflep.com/resource/sound/`。

单选题 input 形态：

```html
<input type="radio" name="rd_8" data-qNum="8" data-id="3">
```

字段对应关系：

| 字段 | 含义 |
|---|---|
| `data-qNum` | 题号 |
| `data-id` | 选项编号，通常 `1` 到 `4` |
| `checked` | 当前已选答案 |

音频播放入口形态：

```html
<a id="btnPlay_<SOUND_KEY>" href="javascript:PlaySound(&quot;<FILE>.mp3&quot;,&quot;<SOUND_KEY>&quot;);">
```

音频 URL 通用形式：

```http
https://wetestoss.sflep.com/resource/sound/<FILE>.mp3
```

---

## 6. saveQuestion：保存单题或音频状态

### 6.1 保存选择题

请求：

```http
POST /api/WelearnTest.aspx?action=saveQuestion&nocache=<随机数>
Content-Type: application/json
```

请求体示例：

```json
{
  "testId": "<TEST_ID>",
  "partNum": 1,
  "answerDetail": {
    "key": "8",
    "value": "3",
    "type": "question",
    "clientTime": "2026/6/22 18:55:30"
  }
}
```

字段说明：

| 字段 | 含义 |
|---|---|
| `key` | 题号 |
| `value` | 选项编号 |
| `type` | `question` 表示普通题目 |
| `clientTime` | 客户端时间 |

### 6.2 保存音频播放次数

请求体示例：

```json
{
  "testId": "<TEST_ID>",
  "partNum": 1,
  "answerDetail": {
    "key": "<SOUND_KEY>",
    "value": 2,
    "type": "sound",
    "clientTime": "2026/6/22 18:50:59"
  }
}
```

字段说明：

| 字段 | 含义 |
|---|---|
| `key` | 音频播放入口 ID |
| `value` | 剩余播放次数 |
| `type` | `sound` 表示音频状态 |

响应结构：

```json
{
  "status": 0,
  "data": {
    "remainSeconds": 0,
    "submited": false
  }
}
```

---

## 7. savePaper：保存或提交整卷

请求：

```http
POST /api/WelearnTest.aspx?action=savePaper&nocache=<随机数>
Content-Type: application/json
```

请求体结构：

```json
{
  "testId": "<TEST_ID>",
  "partNum": 1,
  "Answers": {
    "4": {
      "key": "4",
      "value": "2",
      "type": "question"
    },
    "<SOUND_KEY>": {
      "key": "<SOUND_KEY>",
      "value": "0",
      "type": "sound"
    }
  },
  "Submit": true,
  "ClientTime": "2026/6/22 18:55:33"
}
```

关键字段：

| 字段 | 含义 |
|---|---|
| `Answers` | 整卷答案集合，key 为题号或音频 ID |
| `Submit` | `false` 表示保存，`true` 表示提交 |
| `ClientTime` | 客户端时间 |

本次抓包里的 `savePaper` 使用了：

```json
{
  "Submit": true
}
```

响应结构：

```json
{
  "status": 0,
  "data": {
    "submited": true,
    "remainSeconds": 0,
    "studentName": "<NAME>",
    "studentNo": "<STUDENT_NO>",
    "minutes": 16
  }
}
```

---

## 8. saveLog：日志接口

请求：

```http
POST /api/WelearnTest.aspx?action=saveLog
Content-Type: application/json
```

请求体示例：

```json
{
  "testId": "<TEST_ID>",
  "type": 2,
  "duration": 205,
  "nocache": 0.13590965107536845
}
```

本次抓包中 `saveLog` 响应为：

```json
{
  "status": 1,
  "msg": "参数错误"
}
```

因此目前不能确认该接口是否必须，至少本次页面流程在它失败后仍继续保存和提交了试卷。

---

## 9. 敏感信息风险

`wetest.sflep.com.har` 当前包含以下敏感或半敏感信息：

- `wlToken`；
- `testKey`；
- `Referer` 中的完整测试入口 URL；
- `savePaper` 响应中的姓名；
- `savePaper` 响应中的学号；
- 真实 `testId`；
- 真实作答记录和音频播放记录。

建议不要直接提交原始 HAR。若需要保留到仓库，应先脱敏或只保留本报告。

---

## 10. 可用于后续开发的最小流程

如果要基于这份抓包实现“读取测试并提交”的逻辑，最小流程是：

1. 从任务入口或测试页面 URL 获取 `testKey`。
2. 调用 `POST /api/WelearnTest.aspx?action=initTest&testKey=<TEST_KEY>`。
3. 从响应中读取 `testId`、`partNum`、`paperContent`、`paperAnswer`、`remainSeconds`。
4. 解析 `paperContent` 中的题号、选项、音频 key 和音频文件名。
5. 保存单题时调用 `saveQuestion`。
6. 保存或提交整卷时调用 `savePaper`，用 `Submit=false` 保存，`Submit=true` 提交。

当前缺口：

- HAR 只覆盖了一个测试页面样本，不确定其他题型的 HTML 结构；
- 未确认 `wlToken` 和 `testKey` 的生成来源；
- 未确认 `saveLog` 的正确参数格式；
- `paperAnswer` 是已保存作答状态，不是标准答案，不能用于自动判题。
