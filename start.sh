#!/bin/bash

# ==========================================
# 银行审计多智能体平台启动脚本
# ==========================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 项目根目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$SCRIPT_DIR"

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║            🏦 银行审计多智能体协作平台 v1.0.0                 ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# 检查 Python 版本
echo -e "${YELLOW}📋 检查环境...${NC}"
python_version=$(python3 --version 2>/dev/null || python --version 2>/dev/null || echo "")
if [ -z "$python_version" ]; then
    echo -e "${RED}❌ 未找到 Python，请先安装 Python 3.10+${NC}"
    exit 1
fi
echo -e "${GREEN}✅ $python_version${NC}"

# 检查 poetry
if ! command -v poetry &> /dev/null; then
    echo -e "${YELLOW}⚠️  未找到 poetry，尝试使用 pip 安装...${NC}"
    pip install poetry
fi
echo -e "${GREEN}✅ poetry 已安装${NC}"

# 安装依赖
echo ""
echo -e "${YELLOW}📦 检查并安装依赖...${NC}"
cd "$PROJECT_ROOT"
poetry install --no-root

# 创建必要目录
echo ""
echo -e "${YELLOW}📁 创建数据目录...${NC}"
mkdir -p data/vector_store
mkdir -p data/audit_trails
mkdir -p data/reports
mkdir -p logs
echo -e "${GREEN}✅ 目录已创建${NC}"

# 检查环境变量
if [ ! -f .env ]; then
    echo ""
    echo -e "${YELLOW}⚠️  未找到 .env 文件，从 .env.example 创建...${NC}"
    cp .env.example .env
    echo -e "${YELLOW}   请编辑 .env 文件，填入你的 API Key${NC}"
fi

echo ""
echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}🚀 启动 Web 仪表板...${NC}"
echo ""
echo -e "${BLUE}📊 仪表板地址: ${YELLOW}http://localhost:8501${NC}"
echo -e "${BLUE}💡 按 Ctrl+C 停止服务${NC}"
echo ""
echo -e "${GREEN}══════════════════════════════════════════════════════════════${NC}"
echo ""

# 启动 Streamlit
poetry run streamlit run bank_audit_agents/ui/dashboard.py \
    --server.port=8501 \
    --server.address=0.0.0.0 \
    --server.enableCORS=false \
    --server.enableXsrfProtection=false \
    --theme.base="light" \
    --theme.primaryColor="#1E90FF"
