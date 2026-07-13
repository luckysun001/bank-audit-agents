# 贡献指南

感谢你对本项目的兴趣！欢迎任何形式的贡献。

---

## 📋 贡献方式

### 🐛 报告 Bug
如果你发现了问题，请在 GitHub 提交 Issue，并包含：
- 复现步骤
- 期望行为
- 实际行为
- 环境信息（Python 版本、操作系统等）
- 错误日志

### ✨ 提交新功能
1. 先提交 Issue 讨论你的想法
2. 确认方案后 Fork 项目
3. 提交 Pull Request

### 📝 改进文档
文档优化、错别字修正、翻译等都非常欢迎。

---

## 🚀 开发流程

### 1. 环境准备

```bash
# Fork 并克隆项目
git clone https://github.com/opensource-ai-projects/opensource.git
cd opensource

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate

# 安装开发依赖
pip install -e ".[dev]"
```

### 2. 代码规范

我们遵循以下规范：
- **Python**: PEP 8
- **代码风格**: Black 格式化
- **导入顺序**: isort
- **类型注解**: 尽量使用类型注解
- **文档字符串**: Google 风格

```bash
# 运行代码格式化
black .
isort .

# 运行类型检查
mypy .
```

### 3. 提交 PR

提交 Pull Request 前请确认：
- ✅ 所有测试通过
- ✅ 代码已格式化（black + isort）
- ✅ 相关文档已更新
- ✅ Commit Message 清晰有意义

PR 标题格式：
```
<类型>: <简短描述>

类型：feat / fix / docs / style / refactor / test / chore
```

示例：
```
feat: 添加新的审计规则校验功能
fix: 修复并发任务队列排序问题
docs: 更新快速开始教程
```

---

## 📐 内容贡献规范

### Prompt 模板贡献规范

如果你贡献新的 Prompt 模板：
1. 确保 Prompt 经过实测，效果稳定
2. 附上 2-3 个真实的输入输出示例
3. 说明适用场景和注意事项
4. 标注推荐使用的模型（GPT-4、Claude、通义千问等）

### 文档贡献规范

- 语言清晰简洁，避免技术术语堆砌
- 面向普通用户，默认读者不懂技术
- 每个步骤都有明确的操作指引
- 配上截图和示例会更好

---

## 🤝 行为准则

- 保持友好和尊重
- 接受建设性批评
- 关注对社区最有利的事情
- 耐心解答问题

---

## 📄 许可证

通过贡献，你同意你的贡献将根据项目的开源许可证进行许可。

---

## 💬 有问题？

如果有任何疑问，欢迎提交 Issue 或者发邮件联系维护者。

**感谢你的贡献！** 🎉
