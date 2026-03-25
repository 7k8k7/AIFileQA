# LLM Adapter Proxy

把非 OpenAI 兼容的本地模型 API 翻译成 OpenAI 风格的聊天接口，让 DocQA 直接通过 `openai_compatible` provider 接入。

## 支持的适配器

| 类型 | 说明 | 目标 API |
|------|------|---------|
| `huggingface_tgi` | HuggingFace Text Generation Inference | `/generate_stream`, `/generate`, `/info` |
| `generic` | 可配置的 HTTP JSON 适配器（Jinja2 模板） | JSON over HTTP 的 `POST` 接口 |

## 快速开始

### 1. 配置

```bash
cp config.example.yaml config.yaml
# 编辑 config.yaml，填入你的模型服务地址
```

### 2. 启动

**独立运行：**

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 11435
```

**Docker Compose（推荐）：**

编辑项目根目录 `docker-compose.yml`，取消 `adapter-proxy` 服务的注释。

如果 `adapter-proxy` 容器要去连接宿主机上的模型服务：

- `config.yaml` 里目标地址要写成 `http://host.docker.internal:端口`
- Linux 还要把 `docker-compose.yml` 里 `extra_hosts` 那两行一起取消注释
- macOS / Windows 一般可以直接使用 `host.docker.internal`

然后执行：

```bash
docker compose up -d adapter-proxy
```

### 3. 在 DocQA 中使用

1. 打开 DocQA → 系统设置
2. 添加新 Provider，类型选择 **OpenAI 兼容**
3. Base URL 按实际部署方式填写：
   - `http://adapter-proxy:11435`：DocQA 后端和 `adapter-proxy` 都在同一个 Docker Compose 网络里
   - `http://localhost:11435`：DocQA 后端和 `adapter-proxy` 都是本地直接启动
4. 聊天模型填 config.yaml 中配置的 `model_name`
5. API Key 留空
6. 测试连接 → 设为默认 → 开始聊天

> 这里填的是 DocQA 后端访问代理的地址，不是浏览器访问地址。

## 当前能力边界

- 当前代理实现了 `/v1/models` 和 `/v1/chat/completions`
- 当前**没有**实现 `/v1/embeddings`，所以更适合做聊天联通测试，不是完整的 OpenAI 全接口代理
- DocQA 里的“测试连接”主要依赖 `/v1/models`
  这一步能确认代理服务可达，但不能替代一次真实聊天请求
- `generic` 适配器目前只支持 `POST` + JSON 请求体 + JSON 响应
  还不支持自定义 method、headers、auth、query params、form-data 或非 JSON 响应

## 配置详解

### HuggingFace TGI

```yaml
adapters:
  - model_name: "tgi-qwen"          # DocQA 中填的模型名
    type: "huggingface_tgi"
    base_url: "http://host.docker.internal:8082" # 代理在 Docker、TGI 在宿主机时的写法
```

如果代理本地直接运行，把它改成 `http://localhost:8082` 即可。不要在 Docker 容器里的 `config.yaml` 把宿主机模型地址写成 `localhost`，那会指回代理容器自己。

### 通用 HTTP 适配器

通过 Jinja2 模板自定义请求格式：

```yaml
adapters:
  - model_name: "my-model"
    type: "generic"
    base_url: "http://host.docker.internal:9090"
    chat_endpoint: "/generate"        # 目标端点路径
    request_template: |               # Jinja2 请求体模板
      {"prompt": {{ prompt | tojson }}, "max_tokens": {{ max_tokens }}}
    response_content_path: "result.text"  # 响应中提取内容的 JSON 路径
    stream: false                     # 是否流式
    stream_content_path: "token.text" # 流式时每行提取 token 的路径
    stream_done_field: "done"         # 流式结束标志字段名
```

如果代理本地直接运行，可改成 `http://localhost:9090`。Linux 下用 Docker 跑代理时，记得同时启用 `extra_hosts: ["host.docker.internal:host-gateway"]`。

**模板可用变量：**

| 变量 | 说明 |
|------|------|
| `{{ prompt }}` | messages 拼成的纯文本 |
| `{{ prompt | tojson }}` | 推荐写法，适合直接塞进 JSON 请求体 |
| `{{ messages_json }}` | messages 数组的 JSON 字符串 |
| `{{ temperature }}` | 温度 |
| `{{ max_tokens }}` | 最大 token 数 |
| `{{ model }}` | 模型名称 |

## 运行测试

```bash
pip install -r requirements-dev.txt
pytest -q
```

当前测试覆盖：

- `tests/test_main.py`：代理主接口、模型不存在、错误映射、SSE 返回格式
- `tests/test_generic_adapter.py`：模板渲染、普通响应、流式解析、非流式回退
- `tests/test_huggingface_adapter.py`：TGI 普通/流式返回和 `/info` 降级
- `tests/test_config.py`：配置加载、未知类型跳过、缺字段跳过

## 添加新适配器

1. 在 `adapters/` 目录新建文件，继承 `BaseAdapter`
2. 实现 `chat_completion_stream()` 和 `chat_completion()` 方法
3. 在 `config.py` 的 `ADAPTER_TYPES` 中注册
4. 在 `config.yaml` 中配置使用
