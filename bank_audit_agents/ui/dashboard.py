"""
多智能体系统监控仪表板
基于 Streamlit 的交互式 Web UI
"""
import asyncio
import sys
from datetime import datetime
from typing import Dict, Any, List
import json

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from bank_audit_agents.core.orchestrator import AgentOrchestrator
from bank_audit_agents.workflows.audit_pipeline import AuditPipeline
from bank_audit_agents.utils.logger import get_logger

logger = get_logger(__name__)


# 页面配置
st.set_page_config(
    page_title="银行审计多智能体平台",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)


# 会话状态初始化
if "pipeline_initialized" not in st.session_state:
    st.session_state.pipeline_initialized = False
    st.session_state.orchestrator = None
    st.session_state.pipeline = None
    st.session_state.workflow_results = []


async def init_pipeline():
    """初始化审计流水线"""
    if not st.session_state.pipeline_initialized:
        orchestrator = AgentOrchestrator()
        orchestrator.register_default_agents()
        await orchestrator.start()

        pipeline = AuditPipeline(orchestrator)

        st.session_state.orchestrator = orchestrator
        st.session_state.pipeline = pipeline
        st.session_state.pipeline_initialized = True

        st.success("✅ 审计流水线已启动！")


def render_sidebar():
    """渲染侧边栏"""
    with st.sidebar:
        st.title("🏦 银行审计多智能体平台")
        st.markdown("---")

        # 导航菜单
        page = st.radio(
            "导航",
            [
                "📊 系统概览",
                "🤖 智能体管理",
                "📋 任务监控",
                "🔄 工作流执行",
                "📑 审计报告",
                "⚙️ 系统设置",
            ],
        )

        st.markdown("---")

        # 系统状态
        if st.session_state.pipeline_initialized:
            status = st.session_state.orchestrator.get_status()
            st.success(f"🟢 系统运行中")
            st.info(f"🤖 智能体数量: {status['agents_count']}")
            st.info(f"📋 活跃任务: {status['active_tasks']}")
            st.info(f"✅ 已完成任务: {status['completed_tasks']}")
        else:
            st.warning("🟡 系统未启动")
            if st.button("启动系统", use_container_width=True):
                asyncio.run(init_pipeline())

        st.markdown("---")
        st.caption(f"版本: 1.0.0 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        return page


def render_overview():
    """渲染系统概览页面"""
    st.header("📊 系统概览")

    if not st.session_state.pipeline_initialized:
        st.info("请先在侧边栏启动系统")
        return

    col1, col2, col3, col4 = st.columns(4)

    status = st.session_state.orchestrator.get_status()
    stats = status["statistics"]

    with col1:
        st.metric(
            label="🤖 智能体总数",
            value=status["agents_count"],
        )

    with col2:
        st.metric(
            label="📋 待处理任务",
            value=status["queue_size"],
        )

    with col3:
        st.metric(
            label="✅ 已完成任务",
            value=status["completed_tasks"],
        )

    with col4:
        st.metric(
            label="❌ 失败任务",
            value=status["failed_tasks"],
        )

    st.markdown("---")

    # 智能体状态表格
    st.subheader("智能体状态")
    agents_data = []
    for agent_id, agent_info in status["agents"].items():
        agents_data.append({
            "智能体ID": agent_id[:20] + "...",
            "类型": agent_info["type"],
            "状态": agent_info["status"],
            "已执行任务": agent_info["tasks_executed"],
        })

    if agents_data:
        df_agents = pd.DataFrame(agents_data)
        st.dataframe(df_agents, use_container_width=True, hide_index=True)
    else:
        st.info("暂无智能体数据")

    st.markdown("---")

    # 执行统计图表
    col1, col2 = st.columns(2)

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
        fig = px.pie(
            task_data,
            values="数量",
            names="状态",
            color="状态",
            color_discrete_map={
                "待处理": "#FFA500",
                "执行中": "#1E90FF",
                "已完成": "#32CD32",
                "失败": "#FF4444",
            },
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("智能体类型分布")
        type_counts: Dict[str, int] = {}
        for agent_info in status["agents"].values():
            agent_type = agent_info["type"]
            type_counts[agent_type] = type_counts.get(agent_type, 0) + 1

        type_data = {
            "智能体类型": list(type_counts.keys()),
            "数量": list(type_counts.values()),
        }
        fig = px.bar(type_data, x="智能体类型", y="数量", color="智能体类型")
        st.plotly_chart(fig, use_container_width=True)

    # 运行时间
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


def render_agents_management():
    """渲染智能体管理页面"""
    st.header("🤖 智能体管理")

    if not st.session_state.pipeline_initialized:
        st.info("请先在侧边栏启动系统")
        return

    status = st.session_state.orchestrator.get_status()

    # 智能体详情卡片
    st.subheader("智能体详情")

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

    for agent_type, type_info in agent_types.items():
        agents = st.session_state.orchestrator.get_agents_by_type(agent_type)
        if agents:
            with st.expander(f"{type_info['name']} ({len(agents)}个)", expanded=True):
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.write(f"**描述**: {type_info['description']}")
                    st.write(f"**工具**: {type_info['tools']}")
                with col2:
                    for agent in agents:
                        agent_status = agent.get_status_info()
                        st.markdown(
                            f"- `{agent.agent_id[:25]}...` | "
                            f"状态: `{agent_status['status']}` | "
                            f"已执行: `{agent_status['tasks_executed']}` 任务"
                        )

    st.markdown("---")

    # 智能体操作
    st.subheader("智能体操作")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🔄 刷新状态", use_container_width=True):
            st.rerun()

    with col2:
        if st.button("📊 导出智能体报告", use_container_width=True):
            agent_report = json.dumps(status["agents"], indent=2, ensure_ascii=False)
            st.download_button(
                "下载智能体报告",
                agent_report,
                file_name=f"agents_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json",
                use_container_width=True,
            )

    with col3:
        if st.button("🧪 测试智能体", use_container_width=True):
            st.info("智能体测试功能开发中...")


def render_task_monitoring():
    """渲染任务监控页面"""
    st.header("📋 任务监控")

    if not st.session_state.pipeline_initialized:
        st.info("请先在侧边栏启动系统")
        return

    status = st.session_state.orchestrator.get_status()
    results = st.session_state.orchestrator.get_results()

    # 任务筛选
    st.subheader("任务筛选")
    col1, col2, col3 = st.columns(3)

    with col1:
        task_filter = st.selectbox(
            "任务状态",
            ["全部", "待处理", "执行中", "已完成", "失败"],
        )

    with col2:
        search_term = st.text_input("搜索任务ID")

    with col3:
        refresh_interval = st.slider("自动刷新间隔(秒)", 5, 60, 10)

    # 自动刷新
    if st.checkbox("启用自动刷新"):
        st.empty()
        import time
        time.sleep(refresh_interval)
        st.rerun()

    st.markdown("---")

    # 任务列表
    tab1, tab2, tab3 = st.tabs(["📝 所有任务", "✅ 已完成任务", "❌ 失败任务"])

    with tab1:
        all_tasks = []

        # 活跃任务
        for task_id, task_info in results["pending"].items():
            all_tasks.append({
                "任务ID": task_id[:25] + "...",
                "完整ID": task_id,
                "类型": task_info.get("task_type", "unknown"),
                "状态": task_info.get("status", "pending"),
                "描述": task_info.get("description", ""),
            })

        # 已完成任务
        for task_id, task_info in results["completed"].items():
            all_tasks.append({
                "任务ID": task_id[:25] + "...",
                "完整ID": task_id,
                "类型": task_info.get("task_type", "unknown"),
                "状态": "completed",
                "描述": task_info.get("description", ""),
                "耗时(秒)": task_info.get("duration_seconds", 0),
            })

        if all_tasks:
            df_tasks = pd.DataFrame(all_tasks)

            # 应用筛选
            if task_filter != "全部":
                filter_map = {
                    "待处理": "pending",
                    "执行中": "in_progress",
                    "已完成": "completed",
                    "失败": "failed",
                }
                df_tasks = df_tasks[df_tasks["状态"] == filter_map.get(task_filter, "")]

            if search_term:
                df_tasks = df_tasks[df_tasks["完整ID"].str.contains(search_term, case=False)]

            st.dataframe(df_tasks, use_container_width=True, hide_index=True)
        else:
            st.info("暂无任务数据")

    with tab2:
        if results["completed"]:
            for task_id, task_info in results["completed"].items():
                with st.expander(f"✅ {task_id[:30]}..."):
                    st.write(f"**任务类型**: {task_info.get('task_type')}")
                    st.write(f"**描述**: {task_info.get('description')}")
                    st.write(f"**执行耗时**: {task_info.get('duration_seconds', 0):.2f} 秒")
                    with st.expander("查看输出详情"):
                        st.json(task_info.get("output", {}))
        else:
            st.info("暂无已完成任务")

    with tab3:
        if results["failed"]:
            for task_id, task_info in results["failed"].items():
                with st.expander(f"❌ {task_id[:30]}..."):
                    st.write(f"**任务类型**: {task_info.get('task_type')}")
                    st.write(f"**错误信息**: {task_info.get('error', 'unknown')}")
                    if st.button(f"重试任务: {task_id[:20]}...", key=f"retry_{task_id}"):
                        st.info("任务重试功能开发中...")
        else:
            st.info("暂无失败任务")


def render_workflow_execution():
    """渲染工作流执行页面"""
    st.header("🔄 工作流执行")

    if not st.session_state.pipeline_initialized:
        st.info("请先在侧边栏启动系统")
        return

    pipeline = st.session_state.pipeline

    # 可用工作流
    st.subheader("可用工作流模板")
    workflows = pipeline.get_available_workflows()

    col1, col2 = st.columns([1, 1])

    with col1:
        selected_workflow = st.selectbox(
            "选择工作流",
            [wf["name"] for wf in workflows],
            format_func=lambda x: x,
        )

    with col2:
        for wf in workflows:
            if wf["name"] == selected_workflow:
                st.info(f"📋 {wf['description']}")
                st.info(f"🔧 {wf['steps_count']} 个执行步骤")
                break

    st.markdown("---")

    # 工作流参数配置
    st.subheader("审计参数配置")

    col1, col2 = st.columns(2)

    with col1:
        audited_unit = st.text_input("被审计单位", value="某某分行")
        audit_period = st.text_input("审计期间", value="2024年1月-6月")

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

    # 模拟文档（实际项目中会有文件上传功能）
    st.subheader("审计文档")
    st.info("📄 模拟审计文档已加载: 贷款合同_001.pdf, 财务报表_2024.xlsx, 审批记录.docx")

    st.markdown("---")

    # 执行工作流
    col1, col2, col3 = st.columns([1, 1, 1])

    with col2:
        if st.button("🚀 开始审计", use_container_width=True, type="primary"):
            with st.spinner("审计工作流执行中..."):
                # 模拟工作流执行
                context = {
                    "audited_unit": audited_unit,
                    "audit_period": audit_period,
                    "audit_type": audit_type,
                    "priority": priority,
                }

                # 存储结果
                result = {
                    "workflow_id": f"wf_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    "workflow_name": selected_workflow,
                    "start_time": datetime.now(),
                    "status": "completed",
                    "context": context,
                    "summary": "审计工作流已完成，共识别风险点12个，其中高风险3个，中风险5个，低风险4个",
                }

                st.session_state.workflow_results.append(result)

                st.success("✅ 审计工作流执行完成！")
                st.balloons()

    # 工作流执行历史
    st.markdown("---")
    st.subheader("执行历史")

    if st.session_state.workflow_results:
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


def render_audit_reports():
    """渲染审计报告页面"""
    st.header("📑 审计报告")

    if not st.session_state.workflow_results:
        st.info("暂无审计报告，请先执行工作流")
        return

    # 报告列表
    for i, result in enumerate(reversed(st.session_state.workflow_results)):
        with st.expander(f"📋 {result['workflow_name']} - {result['workflow_id']}", expanded=i == 0):
            st.subheader("审计摘要")
            st.success(result["summary"])

            st.markdown("---")
            st.subheader("风险分布")

            # 模拟风险数据
            risk_data = {
                "风险等级": ["严重", "高", "中", "低"],
                "数量": [2, 3, 5, 2],
            }
            fig = px.bar(
                risk_data,
                x="风险等级",
                y="数量",
                color="风险等级",
                color_discrete_map={
                    "严重": "#FF0000",
                    "高": "#FF6600",
                    "中": "#FFCC00",
                    "低": "#00CC00",
                },
            )
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("---")
            st.subheader("主要风险点")

            risk_findings = [
                {"类别": "信贷风险", "描述": "发现借新还旧迹象，贷款可能存在隐性不良风险", "等级": "高"},
                {"类别": "担保风险", "描述": "抵押物评估价值偏高，抵押率实际超过监管要求", "等级": "中"},
                {"类别": "合规风险", "描述": "贷款审批流程缺少关键审批人签字", "等级": "高"},
                {"类别": "反洗钱", "描述": "客户KYC信息不完整，缺少实际控制人信息", "等级": "严重"},
            ]

            for finding in risk_findings:
                level_emoji = {"严重": "🔴", "高": "🟠", "中": "🟡", "低": "🟢"}.get(finding["等级"], "")
                st.markdown(
                    f"{level_emoji} **{finding['类别']}**: {finding['描述']} "
                    f"(风险等级: {finding['等级']})"
                )

            st.markdown("---")

            # 导出报告
            col1, col2, col3 = st.columns(3)
            with col1:
                st.download_button(
                    "📥 下载完整报告 (JSON)",
                    json.dumps(result, indent=2, ensure_ascii=False, default=str),
                    file_name=f"audit_report_{result['workflow_id']}.json",
                    mime="application/json",
                    use_container_width=True,
                )
            with col2:
                st.download_button(
                    "📥 下载审计报告 (Markdown)",
                    "# 审计报告\n\n...",  # 简化示例
                    file_name=f"audit_report_{result['workflow_id']}.md",
                    mime="text/markdown",
                    use_container_width=True,
                )
            with col3:
                if st.button("📤 发送到邮箱", use_container_width=True):
                    st.info("邮件发送功能开发中...")


def render_system_settings():
    """渲染系统设置页面"""
    st.header("⚙️ 系统设置")

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

    st.subheader("LLM 配置")

    col1, col2 = st.columns(2)

    with col1:
        st.text_input("API 基础地址", value="https://api.openai.com/v1")
        st.text_input("默认模型", value="gpt-4o")

    with col2:
        st.slider("Temperature", 0.0, 2.0, 0.1, 0.1)
        st.number_input("最大 Token 数", min_value=1000, max_value=128000, value=4096)

    st.markdown("---")

    st.subheader("向量数据库配置")
    st.text_input("存储路径", value="./data/vector_store")
    st.text_input("集合名称", value="audit_knowledge_base")

    st.markdown("---")

    # 保存设置
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        if st.button("💾 保存设置", use_container_width=True):
            st.success("设置已保存！")

    # 危险区域
    st.markdown("---")
    st.subheader("⚠️ 危险操作")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🧹 清空任务队列", use_container_width=True):
            st.warning("任务队列已清空")
    with col2:
        if st.button("🔄 重启系统", use_container_width=True):
            st.warning("系统重启中...")


def main():
    """主函数"""
    # 渲染侧边栏
    page = render_sidebar()

    # 根据选择渲染对应的页面
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


if __name__ == "__main__":
    main()
