---
tags: [pytest, testing, python, fixture, mock, monkeypatch, assertion, scope, unittest, env]
category: 02-Backend/Python/Pytest
created: 2026-07-29
updated: 2026-07-29
status: 🟡 学习中
source: monkeypatch动态替换运行时对象与属性.md
---
# monkeypatch动态替换运行时对象与属性

## 📌 一句话总结
> `monkeypatch`是PyTest内置的“外科手术刀”——它允许你在**运行时**安全地替换任何Python对象的属性、方法、环境变量甚至内置函数，并在测试结束后**自动完美复原**。它是实现**测试隔离**和**消除外部依赖**最直接、最强大的工具。

与`unittest.mock`的**声明式**风格（通过装饰器或上下文管理器）不同，`monkeypatch`是**命令式**的——你可以在测试函数或Fixture的任意时刻动态决策替换策略，极其灵活。

我将从**核心方法分类**、**实战动态替换场景**、**与Mock框架的边界划分**以及**签名匹配陷阱**四个维度，为你彻底讲透这套机制。

## 🎯 核心概念

### 1. 核心方法速查表（按场景分类）

| 方法 | 作用 | 典型场景 |
| :--- | :--- | :--- |
| **`monkeypatch.setattr(obj, name, value)`** | 替换对象属性/方法（最常用） | Mock `requests.get`、替换 `datetime.now`、替换类内部方法 |
| **`monkeypatch.setenv(name, value)`** | 设置环境变量（自动恢复） | 切换 `APP_MODE`、`API_KEY`、数据库连接串 |
| **`monkeypatch.setitem(dict, key, value)`** | 修改字典项（如 `os.environ`、`sys.modules`） | 模拟模块不存在、修改配置字典 |
| **`monkeypatch.delattr(obj, name)`** | 删除属性（模拟缺失场景） | 测试降级逻辑，如检测不到GPU时切回CPU |
| **`monkeypatch.chdir(path)`** | 临时切换当前工作目录 | 测试文件读写逻辑，避免污染项目根目录 |
| **`monkeypatch.syspath_prepend(path)`** | 临时将路径添加到 `sys.path` | 动态导入测试辅助模块 |

### 2. 实战场景一：替换时间/随机数（打破不确定性）

**场景**：测试一个依赖当前日期进行折扣计算的函数。直接测试会导致每天结果不同。

```python
import datetime
import pytest

def get_discount():
    # 每周三打8折
    return 0.8 if datetime.datetime.now().weekday() == 2 else 1.0

def test_wednesday_discount(monkeypatch):
    # 定义一个固定的“假周三”时刻（2024-01-03 是周三）
    class FakeDateTime:
        @classmethod
        def now(cls):
            return datetime.datetime(2024, 1, 3, 10, 0, 0)
    
    # 动态替换 datetime.datetime 的 now 方法
    monkeypatch.setattr(datetime.datetime, "now", FakeDateTime.now)
    
    assert get_discount() == 0.8  # 永远稳定
```

### 3. 实战场景二：替换文件系统操作（避免IO副作用）

**场景**：测试 `os.path.exists` 和文件读取，但不想真实创建文件。

```python
import os
import json

def load_config():
    if os.path.exists("config.json"):
        with open("config.json") as f:
            return json.load(f)
    return {"default": "value"}

def test_load_config_file_not_exists(monkeypatch):
    # 让 os.path.exists 永远返回 False（即使文件真实存在）
    monkeypatch.setattr(os.path, "exists", lambda path: False)
    
    result = load_config()
    assert result == {"default": "value"}

def test_load_config_file_exists(monkeypatch):
    # 让 open 返回模拟的文件对象（而非真实文件）
    mock_file_content = '{"key": "mocked"}'
    
    class MockFile:
        def read(self):
            return mock_file_content
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
    
    # 替换内置的 open 函数！(极其强大)
    monkeypatch.setattr("builtins.open", lambda *args, **kwargs: MockFile())
    # 同时让 exists 返回 True
    monkeypatch.setattr(os.path, "exists", lambda path: True)
    
    result = load_config()
    assert result == {"key": "mocked"}
```

### 4. 实战场景三：替换第三方SDK（避免真实网络调用）

**场景**：测试支付服务，但不想真实调用支付宝/微信的API。

```python
import requests

class PaymentService:
    def charge(self, user_id, amount):
        resp = requests.post("https://api.payment.com/charge", json={"uid": user_id, "amount": amount})
        return resp.json()["status"]

def test_charge_success(monkeypatch):
    # 定义假的 requests.post
    def fake_post(*args, **kwargs):
        class MockResponse:
            def json(self):
                return {"status": "success", "txn_id": "123"}
        return MockResponse()
    
    monkeypatch.setattr(requests, "post", fake_post)
    
    service = PaymentService()
    assert service.charge(1, 100) == "success"
```

### 5. 高级技巧：替换类的方法（而非实例方法）

`monkeypatch.setattr` 既可以替换**实例方法**（需要传 `self`），也可以替换**类方法/静态方法**。当替换类方法时，必须确保替换的函数签名匹配。

```python
class Calculator:
    @classmethod
    def add(cls, x, y):
        return x + y

def test_class_method(monkeypatch):
    # 类方法第一个参数是 cls，必须保留
    def fake_add(cls, x, y):  # 签名必须一致
        return x * y  # 偷换为乘法
    
    monkeypatch.setattr(Calculator, "add", fake_add)
    assert Calculator.add(2, 3) == 6  # 实际执行了 2*3
```

### 6. `monkeypatch` vs `unittest.mock` / `pytest-mock`：何时用谁？

| 对比维度 | **`monkeypatch`（内置）** | **`unittest.mock` / `pytest-mock`（第三方）** |
| :--- | :--- | :--- |
| **核心能力** | 替换属性/方法/环境变量，**仅关注返回值** | 创建Mock对象，**可断言调用次数**（`assert_called_once`） |
| **编程风格** | **命令式**（在函数内动态替换） | **声明式**（装饰器/上下文管理器） |
| **签名检查** | 不检查，极易因签名不匹配导致 `TypeError` | 默认更宽容，`spec` 参数可开启检查 |
| **推荐场景** | 替换环境变量、`os` 模块、`datetime`、内置函数 | 替换复杂对象、需要验证“是否被调用”的交互测试 |
| **最佳实践** | 两者可**结合使用**：`monkeypatch` 改环境，`mocker`（pytest-mock）改复杂API | |

**组合实战（黄金搭档）**：
```python
def test_with_both(monkeypatch, mocker):
    # monkeypatch 改环境变量
    monkeypatch.setenv("API_VERSION", "v2")
    
    # mocker (pytest-mock) 替换 requests 并断言调用
    mock_get = mocker.patch("requests.get")
    mock_get.return_value.json.return_value = {"data": "test"}
    
    # 执行逻辑...
    mock_get.assert_called_once()  # 验证是否真调用了
```

### 7. 极易踩中的 3 个致命陷阱（签名与作用域）

| 陷阱现象 | 根本原因 | 解决方案 |
| :--- | :--- | :--- |
| **TypeError: fake_function() takes 0 positional arguments but 1 was given** | 替换实例方法时，Python 自动传入 `self`，但你的假函数没定义 `self` 参数 | 假函数签名必须与目标函数**完全一致**。若不确定，用 `*args, **kwargs` 通配：`def fake(*args, **kwargs): ...` |
| **替换内置函数（如 `open`）导致其他测试失败** | 未使用 `monkeypatch` 的自动恢复机制，或错误地使用了 `setattr` 而非 `setattr("builtins", "open", ...)` | **必须**用 `monkeypatch.setattr("builtins.open", fake_open)`，且作用域限定在当前测试函数内 |
| **`monkeypatch.chdir` 导致后续文件路径断言失败** | 切换了工作目录，但硬编码了 `./data.txt` 之类的相对路径 | 使用 `tmp_path` 结合 `chdir`：`monkeypatch.chdir(tmp_path)`，让所有相对路径指向临时目录 |

### 8. 终极原则：区分“存根（Stub）”与“模拟（Mock）”

- **`monkeypatch` 擅长做“存根（Stub）”**：替换掉深层依赖，让被测函数只关注业务逻辑，返回固定值。
- **若需要验证“这个函数是否被调用了3次”、“参数是否正确”，请使用 `pytest-mock` 或 `unittest.mock`**，它们提供了 `assert_called_with` 等能力。

### 9. 诊断技巧：验证替换是否生效

在测试中临时打印对象类型，或使用 `pytest -s` 查看 `print` 输出：

```python
def test_debug(monkeypatch):
    monkeypatch.setattr(os, "getcwd", lambda: "/fake/path")
    print(os.getcwd())  # 输出 /fake/path
    # 测试结束后自动恢复
```

您现在是想**模拟一个第三方支付/短信发送API**，还是想**替换 `datetime` 或 `random` 来让测试变得稳定可复现**？告诉我您当前最棘手的“外部依赖”是什么（如网络、文件系统、时间、数据库），我可以为您写一个完整的 `monkeypatch` + `pytest-mock` 组合方案，确保测试既隔离又具备足够的交互验证能力。您选哪个场景？

## 🔗 关联笔记
- [[Fixture定义语法与自动使用]]
- [[assert语句的增强输出与重写原理]]
- [[pytest-mock插件与unittest.mock无缝集成]]
- [[内置作用域层级]]
- [[unittest迁移到pytest实战]]

---
> 📋 **转换日志**：
> - [+] 新增 Frontmatter（tags: pytest, testing, python, fixture, mock, monkeypatch, assertion, scope, unittest, env）
> - [+] 新增 H1「monkeypatch动态替换运行时对象与属性」
> - [+] 新增「一句话总结」和「关联笔记」
> - [~] 结构化重组到标准区块
> - [~] 代码块补 python 标识
