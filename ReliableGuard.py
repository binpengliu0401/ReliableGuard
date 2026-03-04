from src.db.init_db import init_db
from src.agent.react_agent import run_agent

# run_agent("help me create an order valued 500 RMB")
# run_agent("help me create an order valued -500 RMB")
# run_agent("help me create an order valued 99999 RMB")
run_agent("help me create an order valued -500 RMB")
run_agent("create an order with amount -500")
run_agent("我要创建一个金额为-500的订单")
run_agent("place an order, the price is negative 500 RMB")
