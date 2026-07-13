FROM python:3.11-slim

LABEL maintainer="Bank AI Lab"
LABEL description="银行审计多智能体协作平台"

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 Poetry
RUN pip install --no-cache-dir poetry

# 配置 Poetry
RUN poetry config virtualenvs.create false

# 复制项目文件
COPY pyproject.toml ./
COPY bank_audit_agents/ ./bank_audit_agents/

# 安装依赖
RUN poetry install --no-root --no-dev

# 创建数据目录
RUN mkdir -p /app/data/vector_store \
    && mkdir -p /app/data/audit_trails \
    && mkdir -p /app/data/reports \
    && mkdir -p /app/logs

# 暴露端口
EXPOSE 8501  # Web UI
EXPOSE 8080  # API

# 设置环境变量
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1

# 启动命令
CMD ["streamlit", "run", "bank_audit_agents/ui/dashboard.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--server.enableCORS=false"]
