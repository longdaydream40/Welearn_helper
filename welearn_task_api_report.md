# WeLearn HAR 抓包分析：任务获取逻辑与接口

> 文件来源：`welearn.har`  
> 目标：定位“任务列表获取逻辑”和相关接口  
> 注意：本文档已省略 Cookie、Token 等敏感字段。

---

## 1. 结论

HAR 中定位到的**任务获取接口**是：

```http
GET https://welearn.sflep.com/ajax/task.aspx
```

核心请求参数：

```text
action=gettasklist
cid=2424
classid=746117
uid=12368818
s=20
pi=0
nocache=随机数
```

完整示例：

```http
GET https://welearn.sflep.com/ajax/task.aspx?action=gettasklist&cid=2424&classid=746117&uid=12368818&s=20&pi=0&nocache=0.8476416166620179
```

---

## 2. 任务获取调用链

页面入口：

```http
GET https://welearn.sflep.com/student/course_info.aspx?cid=2424
```

课程页面中包含任务加载逻辑：

```js
var tskPageSize = 20;
var tskPageIndex = 0;
var hasLoadTask = false;

function LoadTask() {
    if (!hasLoadTask && 746117 > 0) {
        getTask();
        hasLoadTask = true;
    }
}

function getTask() {
    $("#divTaskMore").hide();
    $.ajax({
        url: '/ajax/task.aspx',
        data: "action=gettasklist&cid=2424&classid=746117&uid=12368818&s=" 
              + tskPageSize 
              + "&pi=" + tskPageIndex 
              + "&nocache=" + Math.random(),
        dataType: "json",
        success: function (reData) {
            // 前端根据返回 JSON 拼接任务列表 HTML
        }
    });
}
```

调用流程：

```text
打开课程页 course_info.aspx?cid=2424
        ↓
点击“任务”Tab
        ↓
触发 LoadTask()
        ↓
LoadTask() 只执行一次，防止重复加载
        ↓
调用 getTask()
        ↓
GET /ajax/task.aspx?action=gettasklist...
        ↓
返回 JSON 任务列表
        ↓
前端拼 HTML 显示任务
```

---

## 3. 任务列表接口

### 3.1 请求方法

```http
GET
```

### 3.2 请求路径

```http
/ajax/task.aspx
```

### 3.3 请求参数

| 参数 | 示例值 | 含义 |
|---|---:|---|
| `action` | `gettasklist` | 固定动作，表示获取任务列表 |
| `cid` | `2424` | 课程 ID |
| `classid` | `746117` | 班级 ID |
| `uid` | `12368818` | 用户 ID |
| `s` | `20` | 每页数量，page size |
| `pi` | `0` | 页码索引，疑似从 0 开始 |
| `nocache` | `0.8476416166620179` | 防缓存随机数，来自 `Math.random()` |

### 3.4 请求示例

```http
GET /ajax/task.aspx?action=gettasklist&cid=2424&classid=746117&uid=12368818&s=20&pi=0&nocache=0.8476416166620179 HTTP/2
Host: welearn.sflep.com
```

---

## 4. 接口返回结构

接口返回 JSON，大致结构如下：

```json
{
  "list": [],
  "count": 9,
  "ret": 0
}
```

其中：

| 字段 | 含义 |
|---|---|
| `ret` | 返回状态码，`0` 通常表示成功 |
| `count` | 任务总数 |
| `list` | 任务数组 |

单个任务对象示例：

```json
{
  "TaskName": "全新版高阶听说B2U1",
  "BeginDateStr": "-",
  "EndDateStr": "2026/06/23 23:00",
  "TaskMethod": "StartTaskClassTest(500206138);",
  "TaskTypeName": "测试",
  "TaskHref": "StartTaskClassTest(500206138)",
  "IsExcellentStr": "",
  "CompleteStr": "",
  "Status": "未完成",
  "TaskAction": "<a href='javascript:StartTaskClassTest(500206138);' class='btn btn-sm btn-default'> 开始</a>"
}
```

### 4.1 重要字段说明

| 字段 | 含义 |
|---|---|
| `TaskName` | 任务名称 |
| `BeginDateStr` | 开始时间 |
| `EndDateStr` | 截止时间 |
| `TaskMethod` | 前端点击任务时执行的 JS 方法 |
| `TaskTypeName` | 任务类型，例如测试 |
| `TaskHref` | 任务入口 JS 方法 |
| `Status` | 任务状态，例如未完成 |
| `TaskAction` | 前端按钮 HTML |

---

## 5. 开始任务逻辑

任务列表返回的 `TaskHref` / `TaskMethod` 不是直接 URL，而是 JS 方法：

```js
StartTaskClassTest(500206138)
```

页面中的定义：

```js
function StartTaskClassTest(taskid) {
    top.location.href = "../test/test.aspx?taskid=" + taskid + "&cid=2424";
}
```

因此测试任务的实际进入地址是：

```http
GET https://welearn.sflep.com/test/test.aspx?taskid=500206138&cid=2424
```

通用形式：

```http
GET https://welearn.sflep.com/test/test.aspx?taskid=<任务ID>&cid=<课程ID>
```

---

## 6. HAR 中抓到的任务 ID

| 任务名 | taskid | 状态 | 截止时间 |
|---|---:|---|---|
| 全新版高阶听说B2U1 | `500206138` | 未完成 | `2026/06/23 23:00` |
| 全新版高阶听说B2U7 | `500209569` | 未完成 | `2026/06/26 22:00` |
| 全新版高阶听说B2 Practice Test 2 | `500209477` | 未完成 | `2026/06/29 23:59` |
| 全新版高阶听说B2U5 | `500209555` | 未完成 | `2026/07/05 22:50` |
| 全新版高阶听说B2U2 | `500207262` | 未完成 | `2026/07/06 23:39` |
| 全新版高阶听说B2U3 | `500208399` | 未完成 | `2026/07/06 23:55` |
| 全新版高阶听说B2U4 | `500208404` | 未完成 | `2026/07/06 23:59` |
| 全新版高阶听说B2U6 | 无可开始链接 | 40 分 / 已结束 | `2026/04/30 23:30` |
| 全新版高阶听说B2 Practice Test 1 | 无可开始链接 | 28 分 / 已结束 | `2026/04/09 23:32` |

---

## 7. 接口总结

任务列表接口：

```http
GET /ajax/task.aspx?action=gettasklist&cid=<课程ID>&classid=<班级ID>&uid=<用户ID>&s=20&pi=0&nocache=<随机数>
```

开始测试任务入口：

```http
GET /test/test.aspx?taskid=<任务ID>&cid=<课程ID>
```

---

## 8. 备注

这份 HAR 中主要抓到了：

1. 课程详情页；
2. 任务列表获取接口；
3. 前端任务列表渲染逻辑；
4. 点击“开始任务”后的跳转规则。

但这份 HAR **没有抓到进入测试页后的题目详情接口**。  
如果需要继续分析题目加载接口，需要重新抓包，并在抓包期间点击某个任务的“开始”按钮，进入测试页面后再导出 HAR。
