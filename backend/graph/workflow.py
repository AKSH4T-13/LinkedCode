from langgraph.graph import StateGraph, START, END

from backend.graph.state import LinkedCodeState

from backend.graph.nodes import (
    profile_node,
    candidate_node,
    recommender_node,
    generator_node,
    combine_node
)


# --------------------------------------------------
# BUILD LINKEDCODE WORKFLOW
# --------------------------------------------------

def build_linkedcode_graph():

    workflow = StateGraph(LinkedCodeState)

    # Register nodes
    workflow.add_node("profile", profile_node)
    workflow.add_node("candidates", candidate_node)

    workflow.add_node("agent_1", recommender_node)
    workflow.add_node("agent_2", generator_node)

    workflow.add_node("combine", combine_node)

    # Sequential execution
    workflow.add_edge(START, "profile")
    workflow.add_edge("profile", "candidates")

    # Parallel execution
    workflow.add_edge("candidates", "agent_1")
    workflow.add_edge("candidates", "agent_2")

    # Wait for both agents to finish
    workflow.add_edge(
        ["agent_1", "agent_2"],
        "combine"
    )

    # Finish workflow
    workflow.add_edge("combine", END)

    return workflow.compile()


# --------------------------------------------------
# COMPILED GRAPH
# --------------------------------------------------

linkedcode_graph = build_linkedcode_graph()