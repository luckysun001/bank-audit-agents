# 项目通用 Makefile
# 包含常用的开发、测试、部署命令

.PHONY: help install install-dev test lint format clean build run docs

# 默认目标
.DEFAULT_GOAL := help

# 颜色输出
BLUE := \033[36m
GREEN := \033[32m
YELLOW := \033[33m
RESET := \033[0m

# -----------------------------------------------------------------------------
# 帮助信息
# -----------------------------------------------------------------------------
help: ## 显示帮助信息
	@echo "$(BLUE)╔══════════════════════════════════════════════════╗$(RESET)"
	@echo "$(BLUE)║$(RESET)           $(GREEN)AI 开源项目 - 开发工具$(RESET)                    $(BLUE)║$(RESET)"
	@echo "$(BLUE)╚══════════════════════════════════════════════════╝$(RESET)"
	@echo ""
	@echo "$(YELLOW)使用方法:$(RESET)"
	@echo "  make [目标]"
	@echo ""
	@echo "$(YELLOW)可用目标:$(RESET)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(GREEN)%-20s$(RESET) %s\n", $$1, $$2}'

# -----------------------------------------------------------------------------
# 环境安装
# -----------------------------------------------------------------------------
install: ## 安装生产依赖（Poetry 项目）
	@echo "$(BLUE)→ 安装生产依赖...$(RESET)"
	poetry install --only main
	@echo "$(GREEN)✓ 生产依赖安装完成$(RESET)"

install-dev: ## 安装开发依赖（含测试、格式化等）
	@echo "$(BLUE)→ 安装开发依赖...$(RESET)"
	poetry install --with dev
	@echo "$(GREEN)✓ 开发依赖安装完成$(RESET)"

# -----------------------------------------------------------------------------
# 代码质量
# -----------------------------------------------------------------------------
lint: ## 代码检查 (flake8/pylint/mypy)
	@echo "$(BLUE)→ 运行代码检查...$(RESET)"
	-python -m flake8 . --exclude=venv,__pycache__,tests
	-python -m mypy . --ignore-missing-imports
	@echo "$(GREEN)✓ 代码检查完成$(RESET)"

format: ## 代码格式化 (black + isort)
	@echo "$(BLUE)→ 运行代码格式化...$(RESET)"
	python -m black .
	python -m isort .
	@echo "$(GREEN)✓ 代码格式化完成$(RESET)"

# -----------------------------------------------------------------------------
# 测试
# -----------------------------------------------------------------------------
test: ## 运行所有测试
	@echo "$(BLUE)→ 运行测试...$(RESET)"
	pytest tests/ -v
	@echo "$(GREEN)✓ 测试完成$(RESET)"

test-fast: ## 快速测试（跳过慢测试）
	@echo "$(BLUE)→ 运行快速测试...$(RESET)"
	pytest tests/ -v -m "not slow"

test-cov: ## 测试 + 覆盖率报告
	@echo "$(BLUE)→ 运行测试 + 覆盖率...$(RESET)"
	pytest tests/ --cov=. --cov-report=html --cov-report=term
	@echo "$(GREEN)✓ 测试完成，报告在 htmlcov/index.html$(RESET)"

# -----------------------------------------------------------------------------
# 运行
# -----------------------------------------------------------------------------
run: ## 运行项目（根据项目类型自动选择）
	@echo "$(BLUE)→ 启动项目...$(RESET)"
	@if [ -f "app.py" ]; then \
		streamlit run app.py; \
	elif [ -f "main.py" ]; then \
		python main.py; \
	else \
		echo "$(YELLOW)未找到入口文件，请手动运行$(RESET)"; \
	fi

dev: ## 开发模式运行（热重载）
	@echo "$(BLUE)→ 开发模式启动...$(RESET)"
	@if [ -f "app.py" ]; then \
		streamlit run app.py --server.runOnSave true; \
	else \
		echo "$(YELLOW)未找到入口文件$(RESET)"; \
	fi

# -----------------------------------------------------------------------------
# 文档
# -----------------------------------------------------------------------------
docs: ## 生成文档
	@echo "$(BLUE)→ 生成文档...$(RESET)"
	@if [ -d "docs" ]; then \
		echo "文档在 docs/ 目录"; \
	else \
		echo "暂无 docs 目录"; \
	fi

# -----------------------------------------------------------------------------
# 清理
# -----------------------------------------------------------------------------
clean: ## 清理临时文件
	@echo "$(BLUE)→ 清理临时文件...$(RESET)"
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	rm -rf .coverage htmlcov/ build/ dist/
	@echo "$(GREEN)✓ 清理完成$(RESET)"

# -----------------------------------------------------------------------------
# 构建
# -----------------------------------------------------------------------------
build: ## 构建包
	@echo "$(BLUE)→ 构建项目...$(RESET)"
	python -m build
	@echo "$(GREEN)✓ 构建完成，产物在 dist/$(RESET)"

# -----------------------------------------------------------------------------
# 项目信息
# -----------------------------------------------------------------------------
info: ## 显示项目信息
	@echo "$(BLUE)╔════════════════════════════════════╗$(RESET)"
	@echo "$(BLUE)║$(RESET)          $(GREEN)项目信息$(RESET)                  $(BLUE)║$(RESET)"
	@echo "$(BLUE)╚════════════════════════════════════╝$(RESET)"
	@echo ""
	@echo "Python 版本: $$(python --version)"
	@echo "Pip 版本: $$(pip --version | cut -d' ' -f2)"
	@echo ""
	@echo "目录结构:"
	@ls -la
