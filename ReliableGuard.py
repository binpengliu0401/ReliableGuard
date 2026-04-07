from src.agent.langgraph_agent import run_agent
from src.db.reset_env import reset_env


if __name__ == "__main__":
    reset_env()

    # ecommerce example
    # result = run_agent("create an order with amount 100", domain="ecommerce")

    # reference example
    # result = run_agent(
    #     'parse the PDF at "data/paper1.pdf" with paper_id "paper_001"',
    #     domain="reference",
    # )

    pass
