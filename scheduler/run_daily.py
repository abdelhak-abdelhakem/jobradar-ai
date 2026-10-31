from src.agents.graph import compile_graph
from src.agents.state import initial_state

if __name__ == "__main__":
    compile_graph().invoke(initial_state())
