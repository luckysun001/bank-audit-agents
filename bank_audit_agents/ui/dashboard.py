"""
银行审计多智能体平台 - Web 监控仪表板

本模块基于 Streamlit 构建交互式 Web UI，提供以下核心功能：
- 系统概览：实时监控智能体数量、任务状态、执行统计
- 智能体管理：查看各智能体详情、状态和操作
- 任务监控：追踪任务队列、执行进度和结果
- 工作流执行：配置和启动审计工作流
- 审计报告：查看和导出审计结果报告
- 系统设置：配置智能体参数、LLM 设置等

架构设计：
- 使用 Streamlit 的会话状态(session_state)管理全局状态
- 通过 AgentOrchestrator 与后端多智能体系统交互
- 使用 Pandas + Plotly 实现数据可视化
- 采用响应式布局，支持多列和标签页

启动方式：
    streamlit run bank_audit_agents/ui/dashboard.py
"""
import asyncio
import sys
from datetime import datetime
from typing import Dict, Any, List
import json

# 导入第三方库
import streamlit as st          # Web UI 框架
import pandas as pd              # 数据处理和表格展示
import plotly.express as px     # 交互式图表（柱状图、饼图等）
import plotly.graph_objects as go  # 高级图表功能

# 导入核心模块
from bank_audit_agents.core.orchestrator import AgentOrchestrator  # 智能体协调器
from bank_audit_agents.workflows.audit_pipeline import AuditPipeline  # 审计工作流引擎
from bank_audit_agents.utils.logger import get_logger  # 日志工具

# 初始化日志记录器
logger = get_logger(__name__)


# ==================== 页面配置 ====================
# 设置 Streamlit 页面的基本属性
st.set_page_config(
    page_title="银行审计多智能体平台",  # 浏览器标签页标题
    page_icon="🏦",                    # 页面图标（银行 emoji）
    layout="wide",                    # 宽屏布局模式
    initial_sidebar_state="expanded", # 侧边栏默认展开
)


# ==================== 会话状态管理 ====================
# Streamlit 的 session_state 用于在页面刷新间保持状态
# 这里初始化核心组件的状态变量
if "pipeline_initialized" not in st.session_state:
    st.session_state.pipeline_initialized = False  # 流水线是否已启动
    st.session_state.orchestrator = None           # 协调器实例
    st.session_state.pipeline = None               # 审计流水线实例
    st.session_state.workflow_results = []         # 工作流执行结果列表


# ==================== 核心初始化函数 ====================
async def init_pipeline():
    """初始化审计流水线

    该函数完成以下工作：
    1. 创建 AgentOrchestrator 协调器实例
    2. 注册所有默认智能体（文档解析、风险识别、合规检查等）
    3. 启动协调器（启动消息队列和工作协程）
    4. 创建 AuditPipeline 工作流引擎实例
    5. 将实例保存到会话状态中供后续使用

    注意：由于 Streamlit 是同步框架，需要通过 asyncio.run() 调用此异步函数
    """
    if not st.session_state.pipeline_initialized:
        # 创建协调器并注册默认智能体集合
        orchestrator = AgentOrchestrator()
        orchestrator.register_default_agents()
        await orchestrator.start()

        # 创建审计流水线，关联协调器
        pipeline = AuditPipeline(orchestrator)

        # 将实例保存到会话状态
        st.session_state.orchestrator = orchestrator
        st.session_state.pipeline = pipeline
        st.session_state.pipeline_initialized = True

        # 显示成功提示
        st.success("✅ 审计流水线已启动！")


# ==================== 侧边栏渲染 ====================
def render_sidebar() -> str:
    """渲染侧边栏导航和系统状态

    返回值：
        str: 用户选择的页面名称
    """
    with st.sidebar:
        # 页面标题
        st.title("🏦 银行审计多智能体平台")
        st.markdown("---")  # 分隔线

        # 导航菜单：使用单选按钮实现页面切换
        page = st.radio(
            "导航",
            [
                "📊 系统概览",      # 首页：系统整体状态
                "🤖 智能体管理",    # 查看和管理所有智能体
                "📋 任务监控",      # 追踪任务执行情况
                "🔄 工作流执行",    # 配置和启动审计工作流
                "📑 审计报告",      # 查看和导出审计结果
                "⚙️ 系统设置",      # 系统参数配置
            ],
        )

        st.markdown("---")

        # 系统状态显示区域
        if st.session_state.pipeline_initialized:
            # 获取协调器状态信息
            status = st.session_state.orchestrator.get_status()
            st.success(f"🟢 系统运行中")
            st.info(f"🤖 智能体数量: {status['agents_count']}")
            st.info(f"📋 活跃任务: {status['active_tasks']}")
            st.info(f"✅ 已完成任务: {status['completed_tasks']}")
        else:
            # 系统未启动时显示提示和启动按钮
            st.warning("🟡 系统未启动")
            if st.button("启动系统", use_container_width=True):
                # 调用异步初始化函数
                asyncio.run(init_pipeline())

        st.markdown("---")
        # 显示版本信息和当前时间
        st.caption(f"版本: 1.0.0 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        return page


# ==================== 系统概览页面 ====================
def render_overview():
    """渲染系统概览页面

    页面包含：
    1. 核心指标卡片（智能体数量、待处理/已完成/失败任务数）
    2. 智能体状态表格
    3. 任务完成情况饼图
    4. 智能体类型分布柱状图
    5. 系统运行时间统计
    """
    st.header("📊 系统概览")

    # 检查系统是否已初始化
    if not st.session_state.pipeline_initialized:
        st.info("请先在侧边栏启动系统")
        return

    # 创建4列布局用于显示核心指标
    col1, col2, col3, col4 = st.columns(4)

    # 获取协调器状态数据
    status = st.session_state.orchestrator.get_status()
    stats = status["statistics"]

    # 智能体总数指标
    with col1:
        st.metric(
            label="🤖 智能体总数",
            value=status["agents_count"],
        )

    # 待处理任务数指标
    with col2:
        st.metric(
            label="📋 待处理任务",
            value=status["queue_size"],
        )

    # 已完成任务数指标
    with col3:
        st.metric(
            label="✅ 已完成任务",
            value=status["completed_tasks"],
        )

    # 失败任务数指标
    with col4:
        st.metric(
            label="❌ 失败任务",
            value=status["failed_tasks"],
        )

    st.markdown("---")

    # ==================== 智能体状态表格 ====================
    st.subheader("智能体状态")
    agents_data = []
    # 遍历所有智能体，提取关键信息
    for agent_id, agent_info in status["agents"].items():
        agents_data.append({
            "智能体ID": agent_id[:20] + "...",  # 截断过长的ID
            "类型": agent_info["type"],
            "状态": agent_info["status"],
            "已执行任务": agent_info["tasks_executed"],
        })

    # 使用 Pandas 表格展示智能体列表
    if agents_data:
        df_agents = pd.DataFrame(agents_data)
        st.dataframe(df_agents, use_container_width=True, hide_index=True)
    else:
        st.info("暂无智能体数据")

    st.markdown("---")

    # ==================== 执行统计图表 ====================
    col1, col2 = st.columns(2)

    # 任务完成情况饼图
    with col1:
        st.subheader("任务完成情况")
        task_data = {
            "状态": ["待处理", "执行中", "已完成", "失败"],
            "数量": [
                status["queue_size"],
                status["active_tasks"],
                status["completed_tasks"],
                status["failed_tasks"],
            ],
        }
        # 使用 Plotly 绘制饼图
        fig = px.pie(
            task_data,
            values="数量",
            names="状态",
            color="状态",
            color_discrete_map={
                "待处理": "#FFA500",  # 橙色
                "执行中": "#1E90FF",  # 蓝色
                "已完成": "#32CD32",  # 绿色
                "失败": "#FF4444",    # 红色
            },
        )
        st.plotly_chart(fig, use_container_width=True)

    # 智能体类型分布柱状图
    with col2:
        st.subheader("智能体类型分布")
        type_counts: Dict[str, int] = {}
        # 统计每种类型的智能体数量
        for agent_info in status["agents"].values():
            agent_type = agent_info["type"]
            type_counts[agent_type] = type_counts.get(agent_type, 0) + 1

        type_data = {
            "智能体类型": list(type_counts.keys()),
            "数量": list(type_counts.values()),
        }
        # 使用 Plotly 绘制柱状图
        fig = px.bar(type_data, x="智能体类型", y="数量", color="智能体类型")
        st.plotly_chart(fig, use_container_width=True)

    # ==================== 运行时间统计 ====================
    st.markdown("---")
    st.subheader("运行统计")
    if stats.get("start_time"):
        elapsed = stats["elapsed_seconds"]
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        st.info(
            f"⏱️ 系统已运行: {hours}小时 {minutes}分钟 {seconds}秒 | "
            f"消息交换: {stats['total_messages_exchanged']} 次"
        )


# ==================== 智能体管理页面 ====================
def render_agents_management():
    """渲染智能体管理页面

    页面包含：
    1. 各类型智能体详情卡片（使用折叠面板展示）
    2. 智能体操作按钮（刷新、导出报告、测试）
    """
    st.header("🤖 智能体管理")

    # 检查系统是否已初始化
    if not st.session_state.pipeline_initialized:
        st.info("请先在侧边栏启动系统")
        return

    # 获取协调器状态
    status = st.session_state.orchestrator.get_status()

    # ==================== 智能体详情卡片 ====================
    st.subheader("智能体详情")

    # 定义各智能体类型的元数据（名称、描述、工具）
    agent_types = {
        "document_parser": {
            "name": "📄 文档解析智能体",
            "description": "解析各类审计文档，提取结构化信息",
            "tools": "PDF解析, Word解析, Excel解析, 实体识别",
        },
        "risk_identifier": {
            "name": "⚠️ 风险识别智能体",
            "description": "深度分析文档内容，识别各类审计风险点",
            "tools": "风险模式匹配, 异常检测, 趋势分析",
        },
        "compliance_checker": {
            "name": "✅ 合规检查智能体",
            "description": "对照监管政策和行内制度进行合规性核查",
            "tools": "监管政策匹配, 违规分类, 反洗钱检查",
        },
        "report_writer": {
            "name": "📝 报告撰写智能体",
            "description": "生成标准化审计报告和整改建议",
            "tools": "报告模板引擎, 建议生成器",
        },
        "quality_auditor": {
            "name": "🔍 质量审核智能体",
            "description": "审核其他智能体的输出，确保审计质量",
            "tools": "质量检查, 一致性验证, 完整性检查",
        },
        "task_coordinator": {
            "name": "🎯 任务协调智能体",
            "description": "统筹整个审计流程，协调各智能体协作",
            "tools": "任务规划, 工作流编排, 进度跟踪",
        },
    }

    # 遍历每种智能体类型，显示详情
    for agent_type, type_info in agent_types.items():
        # 根据类型获取所有该类型的智能体实例
        agents = st.session_state.orchestrator.get_agents_by_type(agent_type)
        if agents:
            # 使用折叠面板展示每种类型的智能体详情
            with st.expander(f"{type_info['name']} ({len(agents)}个)", expanded=True):
                col1, col2 = st.columns([1, 2])
                with col1:
                    # 显示智能体类型描述和工具
                    st.write(f"**描述**: {type_info['description']}")
                    st.write(f"**工具**: {type_info['tools']}")
                with col2:
                    # 显示该类型下所有智能体实例的状态信息
                    for agent in agents:
                        agent_status = agent.get_status_info()
                        st.markdown(
                            f"- `{agent.agent_id[:25]}...` | "
                            f"状态: `{agent_status['status']}` | "
                            f"已执行: `{agent_status['tasks_executed']}` 任务"
                        )

    st.markdown("---")

    # ==================== 智能体操作 ====================
    st.subheader("智能体操作")
    col1, col2, col3 = st.columns(3)

    # 刷新状态按钮
    with col1:
        if st.button("🔄 刷新状态", use_container_width=True):
            st.rerun()  # 重新运行整个脚本以获取最新状态

    # 导出智能体报告按钮
    with col2:
        if st.button("📊 导出智能体报告", use_container_width=True):
            # 将智能体状态信息转换为 JSON 格式
            agent_report = json.dumps(status["agents"], indent=2, ensure_ascii=False)
            # 创建下载按钮
            st.download_button(
                "下载智能体报告",
                agent_report,
                file_name=f"agents_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True,
            )

    # 测试智能体按钮（预留功能）
    with col3:
        if st.button("🧪 测试智能体", use_container_width=True):
            st.info("智能体测试功能开发中...")


# ==================== 任务监控页面 ====================
def render_task_monitoring():
    """渲染任务监控页面

    页面包含：
    1. 任务筛选区域（状态筛选、搜索、自动刷新配置）
    2. 任务列表标签页（所有任务、已完成任务、失败任务）
    3. 任务详情展开面板（显示执行耗时、输出详情等）
    """
    st.header("📋 任务监控")

    # 检查系统是否已初始化
    if not st.session_state.pipeline_initialized:
        st.info("请先在侧边栏启动系统")
        return

    # 获取协调器状态和任务执行结果
    status = st.session_state.orchestrator.get_status()
    results = st.session_state.orchestrator.get_results()

    # ==================== 任务筛选区域 ====================
    st.subheader("任务筛选")
    col1, col2, col3 = st.columns(3)

    # 状态筛选下拉框
    with col1:
        task_filter = st.selectbox(
            "任务状态",
            ["全部", "待处理", "执行中", "已完成", "失败"],
        )

    # 任务ID搜索框
    with col2:
        search_term = st.text_input("搜索任务ID")

    # 自动刷新间隔滑块
    with col3:
        refresh_interval = st.slider("自动刷新间隔(秒)", 5, 60, 10)

    # 自动刷新功能实现
    if st.checkbox("启用自动刷新"):
        st.empty()  # 创建一个空容器
        import time
        time.sleep(refresh_interval)  # 等待指定时间
        st.rerun()  # 重新运行脚本刷新页面

    st.markdown("---")

    # ==================== 任务列表标签页 ====================
    tab1, tab2, tab3 = st.tabs(["📝 所有任务", "✅ 已完成任务", "❌ 失败任务"])

    # 标签页1：所有任务
    with tab1:
        all_tasks = []

        # 添加待处理任务
        for task_id, task_info in results["pending"].items():
            all_tasks.append({
                "任务ID": task_id[:25] + "...",  # 截断过长的ID便于显示
                "完整ID": task_id,               # 完整ID用于搜索
                "类型": task_info.get("task_type", "unknown"),
                "状态": task_info.get("status", "pending"),
                "描述": task_info.get("description", ""),
            })

        # 添加已完成任务
        for task_id, task_info in results["completed"].items():
            all_tasks.append({
                "任务ID": task_id[:25] + "...",
                "完整ID": task_id,
                "类型": task_info.get("task_type", "unknown"),
                "状态": "completed",
                "描述": task_info.get("description", ""),
                "耗时(秒)": task_info.get("duration_seconds", 0),
            })

        # 显示任务表格
        if all_tasks:
            df_tasks = pd.DataFrame(all_tasks)

            # 应用状态筛选
            if task_filter != "全部":
                filter_map = {
                    "待处理": "pending",
                    "执行中": "in_progress",
                    "已完成": "completed",
                    "失败": "failed",
                }
                df_tasks = df_tasks[df_tasks["状态"] == filter_map.get(task_filter, "")]

            # 应用搜索筛选
            if search_term:
                df_tasks = df_tasks[df_tasks["完整ID"].str.contains(search_term, case=False)]

            # 显示表格
            st.dataframe(df_tasks, use_container_width=True, hide_index=True)
        else:
            st.info("暂无任务数据")

    # 标签页2：已完成任务（带详情）
    with tab2:
        if results["completed"]:
            for task_id, task_info in results["completed"].items():
                with st.expander(f"✅ {task_id[:30]}..."):
                    st.write(f"**任务类型**: {task_info.get('task_type')}")
                    st.write(f"**描述**: {task_info.get('description')}")
                    st.write(f"**执行耗时**: {task_info.get('duration_seconds', 0):.2f} 秒")
                    # 嵌套展开面板显示输出详情
                    with st.expander("查看输出详情"):
                        st.json(task_info.get("output", {}))
        else:
            st.info("暂无已完成任务")

    # 标签页3：失败任务（带重试按钮）
    with tab3:
        if results["failed"]:
            for task_id, task_info in results["failed"].items():
                with st.expander(f"❌ {task_id[:30]}..."):
                    st.write(f"**任务类型**: {task_info.get('task_type')}")
                    st.write(f"**错误信息**: {task_info.get('error', 'unknown')}")
                    # 重试任务按钮（预留功能）
                    if st.button(f"重试任务: {task_id[:20]}...", key=f"retry_{task_id}"):
                        st.info("任务重试功能开发中...")
        else:
            st.info("暂无失败任务")


# ==================== 工作流执行页面 ====================
def render_workflow_execution():
    """渲染工作流执行页面

    页面包含：
    1. 可用工作流模板选择
    2. 审计参数配置（被审计单位、期间、类型、优先级）
    3. 审计文档上传区域（模拟）
    4. 工作流启动按钮
    5. 执行历史记录
    """
    st.header("🔄 工作流执行")

    # 检查系统是否已初始化
    if not st.session_state.pipeline_initialized:
        st.info("请先在侧边栏启动系统")
        return

    # 获取审计流水线实例
    pipeline = st.session_state.pipeline

    # ==================== 可用工作流模板 ====================
    st.subheader("可用工作流模板")
    # 获取所有可用的工作流模板
    workflows = pipeline.get_available_workflows()

    col1, col2 = st.columns([1, 1])

    # 工作流选择下拉框
    with col1:
        selected_workflow = st.selectbox(
            "选择工作流",
            [wf["name"] for wf in workflows],
            format_func=lambda x: x,
        )

    # 显示选中工作流的详情
    with col2:
        for wf in workflows:
            if wf["name"] == selected_workflow:
                st.info(f"📋 {wf['description']}")
                st.info(f"🔧 {wf['steps_count']} 个执行步骤")
                break

    st.markdown("---")

    # ==================== 审计参数配置 ====================
    st.subheader("审计参数配置")

    col1, col2 = st.columns(2)

    # 基本信息配置
    with col1:
        audited_unit = st.text_input("被审计单位", value="某某分行")
        audit_period = st.text_input("审计期间", value="2024年1月-6月")

    # 审计类型和优先级配置
    with col2:
        audit_type = st.selectbox(
            "审计类型",
            ["常规审计", "专项审计", "离任审计", "后续审计"],
        )
        priority = st.select_slider(
            "优先级",
            options=["低", "中", "高", "紧急"],
            value="中",
        )

    # ==================== 审计文档上传区域 ====================
    # 实际项目中这里会有文件上传组件
    st.subheader("审计文档")
    st.info("📄 模拟审计文档已加载: 贷款合同_001.pdf, 财务报表_2024.xlsx, 审批记录.docx")

    st.markdown("---")

    # ==================== 执行工作流按钮 ====================
    col1, col2, col3 = st.columns([1, 1, 1])

    with col2:
        if st.button("🚀 开始审计", use_container_width=True, type="primary"):
            with st.spinner("审计工作流执行中..."):
                # 构建工作流执行上下文
                context = {
                    "audited_unit": audited_unit,
                    "audit_period": audit_period,
                    "audit_type": audit_type,
                    "priority": priority,
                }

                # 模拟工作流执行结果
                # 实际项目中会调用 pipeline.execute_workflow() 方法
                result = {
                    "workflow_id": f"wf_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    "workflow_name": selected_workflow,
                    "start_time": datetime.now(),
                    "status": "completed",
                    "context": context,
                    "summary": "审计工作流已完成，共识别风险点12个，其中高风险3个，中风险5个，低风险4个",
                }

                # 将结果保存到会话状态
                st.session_state.workflow_results.append(result)

                # 显示成功提示和庆祝动画
                st.success("✅ 审计工作流执行完成！")
                st.balloons()

    # ==================== 工作流执行历史 ====================
    st.markdown("---")
    st.subheader("执行历史")

    if st.session_state.workflow_results:
        # 倒序显示（最新的在前）
        for result in reversed(st.session_state.workflow_results):
            with st.expander(f"✅ {result['workflow_name']} - {result['workflow_id']}"):
                col1, col2 = st.columns(2)
                with col1:
                    st.write(f"**开始时间**: {result['start_time'].strftime('%Y-%m-%d %H:%M:%S')}")
                    st.write(f"**状态**: {result['status']}")
                with col2:
                    st.write(f"**被审计单位**: {result['context']['audited_unit']}")
                    st.write(f"**审计期间**: {result['context']['audit_period']}")
                st.write(f"**摘要**: {result['summary']}")
    else:
        st.info("暂无执行历史记录")


# ==================== 审计报告页面 ====================
def render_audit_reports():
    """渲染审计报告页面

    页面包含：
    1. 审计报告列表（按执行时间倒序）
    2. 审计摘要
    3. 风险分布柱状图
    4. 主要风险点列表
    5. 报告导出功能（JSON、Markdown格式）
    """
    st.header("📑 审计报告")

    # 检查是否有执行结果
    if not st.session_state.workflow_results:
        st.info("暂无审计报告，请先执行工作流")
        return

    # ==================== 报告列表 ====================
    # 倒序遍历，最新的报告显示在最前面
    for i, result in enumerate(reversed(st.session_state.workflow_results)):
        # 默认展开第一个（最新的）报告
        with st.expander(f"📋 {result['workflow_name']} - {result['workflow_id']}", expanded=i == 0):
            # 审计摘要
            st.subheader("审计摘要")
            st.success(result["summary"])

            st.markdown("---")

            # ==================== 风险分布图表 ====================
            st.subheader("风险分布")

            # 模拟风险数据（实际项目中来自工作流执行结果）
            risk_data = {
                "风险等级": ["严重", "高", "中", "低"],
                "数量": [2, 3, 5, 2],
            }
            # 使用 Plotly 绘制柱状图
            fig = px.bar(
                risk_data,
                x="风险等级",
                y="数量",
                color="风险等级",
                color_discrete_map={
                    "严重": "#FF0000",  # 红色
                    "高": "#FF6600",    # 橙色
                    "中": "#FFCC00",    # 黄色
                    "低": "#00CC00",    # 绿色
                },
            )
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("---")

            # ==================== 主要风险点 ====================
            st.subheader("主要风险点")

            # 模拟风险发现数据
            risk_findings = [
                {"类别": "信贷风险", "描述": "发现借新还旧迹象，贷款可能存在隐性不良风险", "等级": "高"},
                {"类别": "担保风险", "描述": "抵押物评估价值偏高，抵押率实际超过监管要求", "等级": "中"},
                {"类别": "合规风险", "描述": "贷款审批流程缺少关键审批人签字", "等级": "高"},
                {"类别": "反洗钱", "描述": "客户KYC信息不完整，缺少实际控制人信息", "等级": "严重"},
            ]

            # 逐个显示风险点，带颜色标识
            for finding in risk_findings:
                level_emoji = {"严重": "🔴", "高": "🟠", "中": "🟡", "低": "🟢"}.get(finding["等级"], "")
                st.markdown(
                    f"{level_emoji} **{finding['类别']}**: {finding['描述']} "
                    f"(风险等级: {finding['等级']})"
                )

            st.markdown("---")

            # ==================== 报告导出功能 ====================
            col1, col2, col3 = st.columns(3)

            # 导出 JSON 格式报告
            with col1:
                st.download_button(
                    "📥 下载完整报告 (JSON)",
                    json.dumps(result, indent=2, ensure_ascii=False, default=str),
                    file_name=f"audit_report_{result['workflow_id']}.json",
                    mime="application/json",
                    use_container_width=True,
                )

            # 导出 Markdown 格式报告
            with col2:
                st.download_button(
                    "📥 下载审计报告 (Markdown)",
                    "# 审计报告\n\n...",  # 简化示例，实际项目中会生成完整报告
                    file_name=f"audit_report_{result['workflow_id']}.md",
                    mime="text/markdown",
                    use_container_width=True,
                )

            # 发送邮件功能（预留）
            with col3:
                if st.button("📤 发送到邮箱", use_container_width=True):
                    st.info("邮件发送功能开发中...")


# ==================== 系统设置页面 ====================
def render_system_settings():
    """渲染系统设置页面

    页面包含：
    1. 智能体配置（并行任务数、超时时间、重试设置等）
    2. LLM 配置（API地址、模型、温度、Token限制等）
    3. 向量数据库配置（存储路径、集合名称）
    4. 保存设置按钮
    5. 危险操作区域（清空任务队列、重启系统）

    注意：当前版本为演示版本，设置修改不会持久化到配置文件
    """
    st.header("⚙️ 系统设置")

    # ==================== 智能体配置 ====================
    st.subheader("智能体配置")

    col1, col2 = st.columns(2)

    with col1:
        st.number_input("最大并行任务数", min_value=1, max_value=20, value=5)
        st.number_input("任务超时时间(秒)", min_value=30, max_value=600, value=120)
        st.checkbox("启用自动重试", value=True)

    with col2:
        st.number_input("最大重试次数", min_value=1, max_value=10, value=3)
        st.selectbox("日志级别", ["DEBUG", "INFO", "WARNING", "ERROR"], index=1)
        st.checkbox("启用质量审核", value=True)

    st.markdown("---")

    # ==================== LLM 配置 ====================
    st.subheader("LLM 配置")

    col1, col2 = st.columns(2)

    with col1:
        st.text_input("API 基础地址", value="https://api.openai.com/v1")
        st.text_input("默认模型", value="gpt-4o")

    with col2:
        # Temperature 参数：控制生成文本的随机性
        # 0 = 确定性输出，2 = 高度随机输出
        st.slider("Temperature", 0.0, 2.0, 0.1, 0.1)
        st.number_input("最大 Token 数", min_value=1000, max_value=128000, value=4096)

    st.markdown("---")

    # ==================== 向量数据库配置 ====================
    st.subheader("向量数据库配置")
    st.text_input("存储路径", value="./data/vector_store")
    st.text_input("集合名称", value="audit_knowledge_base")

    st.markdown("---")

    # ==================== 保存设置 ====================
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("💾 保存设置", use_container_width=True):
            st.success("设置已保存！")

    # ==================== 危险操作区域 ====================
    st.markdown("---")
    st.subheader("⚠️ 危险操作")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🧹 清空任务队列", use_container_width=True):
            st.warning("任务队列已清空")
    with col2:
        if st.button("🔄 重启系统", use_container_width=True):
            st.warning("系统重启中...")


# ==================== 主函数 ====================
def main():
    """主函数：应用入口

    执行流程：
    1. 渲染侧边栏导航
    2. 根据用户选择的页面渲染对应的内容
    3. 通过 Streamlit 的会话状态管理全局状态
    """
    # 渲染侧边栏，获取用户选择的页面
    page = render_sidebar()

    # 根据用户选择渲染对应的页面
    if page == "📊 系统概览":
        render_overview()
    elif page == "🤖 智能体管理":
        render_agents_management()
    elif page == "📋 任务监控":
        render_task_monitoring()
    elif page == "🔄 工作流执行":
        render_workflow_execution()
    elif page == "📑 审计报告":
        render_audit_reports()
    elif page == "⚙️ 系统设置":
        render_system_settings()


# 应用启动入口
if __name__ == "__main__":
    main()
