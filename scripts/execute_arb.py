"""
PolyHunter - 诺贝尔和平奖 2026 套利执行
==========================================
策略：买入所有候选人的 YES token
原理：只要任一候选人获奖，持有的该 YES token 价值 $1
"""

import asyncio
import json
import os
import sys

# 设置代理 — Clash Verge 端口 7897
os.environ["HTTP_PROXY"] = "http://127.0.0.1:7897"
os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7897"

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

import httpx
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import ApiCreds, OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY


INVESTMENT = 10.0  # 投入金额（美元）


async def get_nobel_markets():
    """获取诺贝尔和平奖所有候选人市场数据"""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            "https://gamma-api.polymarket.com/events",
            params={"active": "true", "closed": "false", "limit": 500},
            timeout=30,
        )
        events = resp.json()

    for event in events:
        if "nobel peace" in event.get("title", "").lower():
            markets = event.get("markets", [])
            candidates = []
            for m in markets:
                try:
                    prices = json.loads(m.get("outcomePrices", "[]"))
                    clob_ids = json.loads(m.get("clobTokenIds", "[]"))
                    yes_price = float(prices[0])
                    if yes_price > 0 and len(clob_ids) >= 1:
                        candidates.append({
                            "name": m.get("groupItemTitle", ""),
                            "token_id": clob_ids[0],
                            "price": yes_price,
                        })
                except:
                    continue
            return event.get("title", ""), candidates
    return None, []


def create_client():
    """创建认证过的 Polymarket 交易客户端"""
    pk = os.getenv("POLYMARKET_PRIVATE_KEY", "")
    if not pk.startswith("0x"):
        pk = "0x" + pk

    client = ClobClient(
        host="https://clob.polymarket.com",
        key=pk,
        chain_id=137,
        signature_type=0,
        funder=os.getenv("POLYMARKET_FUNDER", ""),
    )
    client.set_api_creds(ApiCreds(
        api_key=os.getenv("POLYMARKET_API_KEY", ""),
        api_secret=os.getenv("POLYMARKET_API_SECRET", ""),
        api_passphrase=os.getenv("POLYMARKET_API_PASSPHRASE", ""),
    ))
    return client


def main():
    # 1. 获取市场数据
    print("正在获取诺贝尔和平奖市场数据...")
    title, candidates = asyncio.run(get_nobel_markets())
    if not candidates:
        print("ERROR: 未找到诺贝尔和平奖市场")
        return

    print(f"事件: {title}")
    print(f"候选人: {len(candidates)} 个")

    total_yes = sum(c["price"] for c in candidates)
    shares = INVESTMENT / total_yes
    gap = 1.0 - total_yes
    expected_profit = shares * gap

    print()
    print(f"=== 套利计划 ===")
    print(f"投入: ${INVESTMENT}")
    print(f"YES 总和: ${total_yes:.4f}")
    print(f"差距: {gap*100:.2f}%")
    print(f"购买份数: {shares:.2f}")
    print(f"保证收回: ${shares:.2f}")
    print(f"预期毛利: ${expected_profit:.2f}")
    print()

    # 排序：价格从低到高
    candidates.sort(key=lambda x: x["price"])

    for c in candidates:
        cost = c["price"] * shares
        print(f"  {c['name'][:30]:30s} YES=${c['price']:.3f}  花费=${cost:.3f}")

    print()
    print(f"共 {len(candidates)} 笔限价单")
    print()

    # 2. 确认执行
    confirm = input("确认执行？(y/n): ").strip().lower()
    if confirm != "y":
        print("已取消")
        return

    # 3. 创建交易客户端
    print()
    print("正在连接 Polymarket...")
    client = create_client()

    # 4. 逐个下单
    print("开始下单...")
    print()

    success_count = 0
    fail_count = 0
    total_spent = 0

    for i, c in enumerate(candidates):
        size = round(shares, 2)  # 每个候选人买相同份数
        price = c["price"]

        if size < 1:
            size = 1  # 最小下单量

        try:
            order_args = OrderArgs(
                price=price,
                size=size,
                side=BUY,
                token_id=c["token_id"],
            )
            signed_order = client.create_order(order_args)
            resp = client.post_order(signed_order, OrderType.GTC)

            order_id = resp.get("orderID", "unknown")
            print(f"  [{i+1}/{len(candidates)}] {c['name'][:25]:25s} ✅ 已下单 (price=${price:.3f} size={size}) order={order_id[:12]}")
            success_count += 1
            total_spent += price * size
        except Exception as e:
            print(f"  [{i+1}/{len(candidates)}] {c['name'][:25]:25s} ❌ 失败: {e}")
            fail_count += 1

    print()
    print(f"=== 执行结果 ===")
    print(f"成功: {success_count} 笔")
    print(f"失败: {fail_count} 笔")
    print(f"预计花费: ${total_spent:.2f}")
    print()

    if success_count > 0:
        print("订单已提交为限价单(GTC)，等待成交。")
        print("你可以在 Polymarket 网站或 Dashboard 查看订单状态。")


if __name__ == "__main__":
    main()
