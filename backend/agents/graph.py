"""LangGraph StateGraph definition and workflow compilation."""

from typing import Literal
from langgraph.graph import END, START, StateGraph

from agents.memory_agent import get_checkpointer
from agents.planner_agent import planner_agent_node
from agents.recommendation_agent import recommendation_agent_node
from agents.review_agent import review_agent_node
from agents.state import AgentState
from agents.supervisor import supervisor_node
from agents.task_agent import task_agent_node


def route_to_agent(state: AgentState) -> Literal["task_agent", "planner_agent", "recommendation_agent", "review_agent"]:
    """Conditional routing function after supervisor classification."""
    active = state.get("active_agent", "task_agent")
    if active in ("task_agent", "planner_agent", "recommendation_agent", "review_agent"):
        return active  # type: ignore
    return "task_agent"


def build_agent_graph(checkpointer=None):
    """Builds and compiles the full multi-agent StateGraph with checkpointer."""
    workflow = StateGraph(AgentState)

    # 1. Add all nodes
    workflow.add_node("supervisor", supervisor_node)
    workflow.add_node("task_agent", task_agent_node)
    workflow.add_node("planner_agent", planner_agent_node)
    workflow.add_node("recommendation_agent", recommendation_agent_node)
    workflow.add_node("review_agent", review_agent_node)

    # 2. Add entry edge
    workflow.add_edge(START, "supervisor")

    # 3. Add conditional router edge from supervisor
    workflow.add_conditional_edges(
        "supervisor",
        route_to_agent,
        {
            "task_agent": "task_agent",
            "planner_agent": "planner_agent",
            "recommendation_agent": "recommendation_agent",
            "review_agent": "review_agent",
        },
    )

    # 4. Add exit edges from specialists to END
    workflow.add_edge("task_agent", END)
    workflow.add_edge("planner_agent", END)
    workflow.add_edge("recommendation_agent", END)
    workflow.add_edge("review_agent", END)

    cp = checkpointer if checkpointer is not None else get_checkpointer()
    return workflow.compile(checkpointer=cp)


# Pre-compiled graph instance
agent_graph = build_agent_graph()
