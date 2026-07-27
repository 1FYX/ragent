# Python 异步编程指南

本文档介绍 Python 中的异步编程，包括 asyncio、协程、事件循环等核心概念。

## 1. 什么是异步编程

异步编程是一种并发编程模型，允许程序在等待 I/O 操作（如网络请求、文件读写）时
不阻塞主线程，从而提高程序的吞吐量。Python 通过 `asyncio` 库提供原生支持。

异步编程特别适合 I/O 密集型任务，例如：
- 网络爬虫（同时抓取多个网页）
- Web 服务器（同时处理多个请求）
- 数据库批量查询

## 2. asyncio 核心概念

### 2.1 事件循环（Event Loop）

事件循环是异步编程的核心，负责调度和执行任务。它会不断检查是否有任务完成，
完成后执行对应的回调。

启动事件循环的常见方式：

```python
import asyncio

async def main():
    print("hello")

asyncio.run(main())
```

### 2.2 协程（Coroutine）

用 `async def` 定义的函数就是协程。协程不会立即执行，必须由事件循环调度。
调用协程会返回一个协程对象，需要用 `await` 来获取结果。

```python
async def fetch_data():
    await asyncio.sleep(1)  # 模拟 I/O
    return {"data": 42}

result = await fetch_data()
```

### 2.3 await 关键字

`await` 只能在 `async def` 函数内使用，用于等待一个可等待对象（协程、Task、Future）。
遇到 `await` 时，控制权交还给事件循环，事件循环可以去执行其他任务。

## 3. 并发执行多个任务

### 3.1 asyncio.gather

同时运行多个协程，等待全部完成：

```python
async def task(name, delay):
    await asyncio.sleep(delay)
    return f"{name} 完成"

results = await asyncio.gather(
    task("A", 2),
    task("B", 1),
    task("C", 3),
)
# 总耗时约 3 秒（取最长的），而非 2+1+3=6 秒
```

### 3.2 asyncio.create_task

把协程包装成 Task，立即调度执行：

```python
task = asyncio.create_task(fetch_data())
# 此时 task 已经在后台开始执行
result = await task
```

## 4. 异步上下文管理器

用 `async with` 管理异步资源（如数据库连接、HTTP 客户端）：

```python
class AsyncDB:
    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.close()

async with AsyncDB() as db:
    await db.query("SELECT 1")
```

## 5. 常见陷阱

1. **在同步代码中调用协程**：直接调用 `fetch_data()` 不会执行，只会返回协程对象。
2. **阻塞事件循环**：在协程里用 `time.sleep()` 会阻塞整个事件循环，应该用 `asyncio.sleep()`。
3. **忘记 await**：调用协程不加 await，任务不会执行，且会有 "coroutine was never awaited" 警告。

## 6. 适用场景与不适用场景

适合：I/O 密集型（网络、磁盘、数据库）。
不适合：CPU 密集型（大量计算），应该用多进程（multiprocessing）。
