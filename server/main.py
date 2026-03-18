from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime, timedelta
import uuid
from mock_data import inventory_items, orders, demand_forecasts, backlog_items, spending_summary, monthly_spending, category_spending, recent_transactions, purchase_orders

app = FastAPI(title="Factory Inventory Management System")

# Quarter mapping for date filtering
QUARTER_MAP = {
    'Q1-2025': ['2025-01', '2025-02', '2025-03'],
    'Q2-2025': ['2025-04', '2025-05', '2025-06'],
    'Q3-2025': ['2025-07', '2025-08', '2025-09'],
    'Q4-2025': ['2025-10', '2025-11', '2025-12']
}

def filter_by_month(items: list, month: Optional[str]) -> list:
    """Filter items by month/quarter based on order_date field"""
    if not month or month == 'all':
        return items

    if month.startswith('Q'):
        # Handle quarters
        if month in QUARTER_MAP:
            months = QUARTER_MAP[month]
            return [item for item in items if any(m in item.get('order_date', '') for m in months)]
    else:
        # Direct month match
        return [item for item in items if month in item.get('order_date', '')]

    return items

def apply_filters(items: list, warehouse: Optional[str] = None, category: Optional[str] = None,
                 status: Optional[str] = None) -> list:
    """Apply common filters to a list of items"""
    filtered = items

    if warehouse and warehouse != 'all':
        filtered = [item for item in filtered if item.get('warehouse') == warehouse]

    if category and category != 'all':
        filtered = [item for item in filtered if item.get('category', '').lower() == category.lower()]

    if status and status != 'all':
        filtered = [item for item in filtered if item.get('status', '').lower() == status.lower()]

    return filtered

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Data models
class InventoryItem(BaseModel):
    id: str
    sku: str
    name: str
    category: str
    warehouse: str
    quantity_on_hand: int
    reorder_point: int
    unit_cost: float
    location: str
    last_updated: str

class Order(BaseModel):
    id: str
    order_number: str
    customer: str
    items: List[dict]
    status: str
    order_date: str
    expected_delivery: str
    total_value: float
    actual_delivery: Optional[str] = None
    warehouse: Optional[str] = None
    category: Optional[str] = None

class DemandForecast(BaseModel):
    id: str
    item_sku: str
    item_name: str
    current_demand: int
    forecasted_demand: int
    trend: str
    period: str
    unit_cost: float

class BacklogItem(BaseModel):
    id: str
    order_id: str
    item_sku: str
    item_name: str
    quantity_needed: int
    quantity_available: int
    days_delayed: int
    priority: str
    has_purchase_order: Optional[bool] = False

class PurchaseOrder(BaseModel):
    id: str
    backlog_item_id: str
    supplier_name: str
    quantity: int
    unit_cost: float
    expected_delivery_date: str
    status: str
    created_date: str
    notes: Optional[str] = None

class CreatePurchaseOrderRequest(BaseModel):
    backlog_item_id: str
    supplier_name: str
    quantity: int
    unit_cost: float
    expected_delivery_date: str
    notes: Optional[str] = None

# API endpoints
@app.get("/")
def root():
    return {"message": "Factory Inventory Management System API", "version": "1.0.0"}

@app.get("/api/inventory", response_model=List[InventoryItem])
def get_inventory(
    warehouse: Optional[str] = None,
    category: Optional[str] = None
):
    """Get all inventory items with optional filtering"""
    return apply_filters(inventory_items, warehouse, category)

@app.get("/api/inventory/{item_id}", response_model=InventoryItem)
def get_inventory_item(item_id: str):
    """Get a specific inventory item"""
    item = next((item for item in inventory_items if item["id"] == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

@app.get("/api/orders", response_model=List[Order])
def get_orders(
    warehouse: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    month: Optional[str] = None
):
    """Get all orders with optional filtering"""
    filtered_orders = apply_filters(orders, warehouse, category, status)
    filtered_orders = filter_by_month(filtered_orders, month)
    return filtered_orders

@app.get("/api/orders/{order_id}", response_model=Order)
def get_order(order_id: str):
    """Get a specific order"""
    order = next((order for order in orders if order["id"] == order_id), None)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

@app.get("/api/demand", response_model=List[DemandForecast])
def get_demand_forecasts():
    """Get demand forecasts"""
    return demand_forecasts

@app.get("/api/backlog", response_model=List[BacklogItem])
def get_backlog():
    """Get backlog items with purchase order status"""
    # Add has_purchase_order flag to each backlog item
    result = []
    for item in backlog_items:
        item_dict = dict(item)
        # Check if this backlog item has a purchase order
        has_po = any(po["backlog_item_id"] == item["id"] for po in purchase_orders)
        item_dict["has_purchase_order"] = has_po
        result.append(item_dict)
    return result

@app.get("/api/dashboard/summary")
def get_dashboard_summary(
    warehouse: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    month: Optional[str] = None
):
    """Get summary statistics for dashboard with optional filtering"""
    # Filter inventory
    filtered_inventory = apply_filters(inventory_items, warehouse, category)

    # Filter orders
    filtered_orders = apply_filters(orders, warehouse, category, status)
    filtered_orders = filter_by_month(filtered_orders, month)

    total_inventory_value = sum(item["quantity_on_hand"] * item["unit_cost"] for item in filtered_inventory)
    low_stock_items = len([item for item in filtered_inventory if item["quantity_on_hand"] <= item["reorder_point"]])
    pending_orders = len([order for order in filtered_orders if order["status"] in ["Processing", "Backordered"]])
    total_backlog_items = len(backlog_items)

    return {
        "total_inventory_value": round(total_inventory_value, 2),
        "low_stock_items": low_stock_items,
        "pending_orders": pending_orders,
        "total_backlog_items": total_backlog_items,
        "total_orders_value": sum(order["total_value"] for order in filtered_orders)
    }

@app.get("/api/spending/summary")
def get_spending_summary():
    """Get spending summary statistics"""
    return spending_summary

@app.get("/api/spending/monthly")
def get_monthly_spending():
    """Get monthly spending breakdown"""
    return monthly_spending

@app.get("/api/spending/categories")
def get_category_spending():
    """Get spending by category"""
    return category_spending

@app.get("/api/spending/transactions")
def get_recent_transactions():
    """Get recent transactions"""
    return recent_transactions

@app.get("/api/reports/quarterly")
def get_quarterly_reports():
    """Get quarterly performance reports"""
    # Calculate quarterly statistics from orders
    quarters = {}

    for order in orders:
        order_date = order.get('order_date', '')
        # Determine quarter
        if '2025-01' in order_date or '2025-02' in order_date or '2025-03' in order_date:
            quarter = 'Q1-2025'
        elif '2025-04' in order_date or '2025-05' in order_date or '2025-06' in order_date:
            quarter = 'Q2-2025'
        elif '2025-07' in order_date or '2025-08' in order_date or '2025-09' in order_date:
            quarter = 'Q3-2025'
        elif '2025-10' in order_date or '2025-11' in order_date or '2025-12' in order_date:
            quarter = 'Q4-2025'
        else:
            continue

        if quarter not in quarters:
            quarters[quarter] = {
                'quarter': quarter,
                'total_orders': 0,
                'total_revenue': 0,
                'delivered_orders': 0,
                'avg_order_value': 0
            }

        quarters[quarter]['total_orders'] += 1
        quarters[quarter]['total_revenue'] += order.get('total_value', 0)
        if order.get('status') == 'Delivered':
            quarters[quarter]['delivered_orders'] += 1

    # Calculate averages and fulfillment rate
    result = []
    for q, data in quarters.items():
        if data['total_orders'] > 0:
            data['avg_order_value'] = round(data['total_revenue'] / data['total_orders'], 2)
            data['fulfillment_rate'] = round((data['delivered_orders'] / data['total_orders']) * 100, 1)
        result.append(data)

    # Sort by quarter
    result.sort(key=lambda x: x['quarter'])
    return result

@app.get("/api/reports/monthly-trends")
def get_monthly_trends():
    """Get month-over-month trends"""
    months = {}

    for order in orders:
        order_date = order.get('order_date', '')
        if not order_date:
            continue

        # Extract month (format: YYYY-MM-DD)
        month = order_date[:7]  # Gets YYYY-MM

        if month not in months:
            months[month] = {
                'month': month,
                'order_count': 0,
                'revenue': 0,
                'delivered_count': 0
            }

        months[month]['order_count'] += 1
        months[month]['revenue'] += order.get('total_value', 0)
        if order.get('status') == 'Delivered':
            months[month]['delivered_count'] += 1

    # Convert to list and sort
    result = list(months.values())
    result.sort(key=lambda x: x['month'])
    return result

# --- Restocking models and endpoints ---

class RestockingRecommendation(BaseModel):
    sku: str
    name: str
    unit_cost: float
    quantity_on_hand: int
    forecasted_demand: int
    demand_gap: int
    restock_quantity: int
    total_cost: float
    priority_score: float
    selected: bool

class RestockingBudgetResponse(BaseModel):
    min_budget: float
    max_budget: float
    current_budget: float
    recommendations: List[RestockingRecommendation]
    total_selected_cost: float
    total_selected_items: int

class SubmitRestockingOrderItem(BaseModel):
    sku: str
    name: str
    quantity: int
    unit_cost: float

class SubmitRestockingOrderRequest(BaseModel):
    items: List[SubmitRestockingOrderItem]
    total_cost: float

class RestockingOrder(BaseModel):
    id: str
    order_number: str
    items: List[dict]
    total_cost: float
    status: str
    submitted_date: str
    expected_delivery: str

# In-memory store for submitted restocking orders
restocking_orders: list = []

@app.get("/api/restocking/recommendations", response_model=RestockingBudgetResponse)
def get_restocking_recommendations(budget: float = 50000.0):
    """Get restocking recommendations constrained by budget.

    Algorithm: builds recommendations from demand forecasts (gap between
    forecasted demand and current inventory) plus low-stock inventory items
    not covered by forecasts, then greedily selects by priority score."""
    # Build inventory lookup by SKU
    inv_by_sku = {item["sku"]: item for item in inventory_items}

    recommendations = []
    forecast_skus = set()

    # 1. Recommendations from demand forecasts
    for fc in demand_forecasts:
        sku = fc["item_sku"]
        forecast_skus.add(sku)
        inv = inv_by_sku.get(sku)
        qty_on_hand = inv["quantity_on_hand"] if inv else 0
        forecasted = fc["forecasted_demand"]
        demand_gap = max(0, forecasted - qty_on_hand)
        if demand_gap <= 0:
            continue
        unit_cost = fc["unit_cost"]
        total_cost = demand_gap * unit_cost
        priority_score = demand_gap * unit_cost
        recommendations.append({
            "sku": sku,
            "name": fc["item_name"],
            "unit_cost": unit_cost,
            "quantity_on_hand": qty_on_hand,
            "forecasted_demand": forecasted,
            "demand_gap": demand_gap,
            "restock_quantity": demand_gap,
            "total_cost": round(total_cost, 2),
            "priority_score": round(priority_score, 2),
            "selected": False,
        })

    # 2. Low-stock inventory items not already in forecast list
    for item in inventory_items:
        if item["sku"] in forecast_skus:
            continue
        if item["quantity_on_hand"] <= item["reorder_point"]:
            demand_gap = item["reorder_point"] * 2 - item["quantity_on_hand"]
            if demand_gap <= 0:
                continue
            total_cost = demand_gap * item["unit_cost"]
            priority_score = demand_gap * item["unit_cost"]
            recommendations.append({
                "sku": item["sku"],
                "name": item["name"],
                "unit_cost": item["unit_cost"],
                "quantity_on_hand": item["quantity_on_hand"],
                "forecasted_demand": item["reorder_point"] * 2,
                "demand_gap": demand_gap,
                "restock_quantity": demand_gap,
                "total_cost": round(total_cost, 2),
                "priority_score": round(priority_score, 2),
                "selected": False,
            })

    # 3. Sort by priority_score descending
    recommendations.sort(key=lambda r: r["priority_score"], reverse=True)

    if not recommendations:
        return RestockingBudgetResponse(
            min_budget=0, max_budget=0, current_budget=budget,
            recommendations=[], total_selected_cost=0, total_selected_items=0
        )

    min_budget = min(r["total_cost"] for r in recommendations)
    max_budget = sum(r["total_cost"] for r in recommendations)

    # 4. Greedy selection within budget
    remaining = budget
    total_selected_cost = 0.0
    total_selected_items = 0
    for rec in recommendations:
        if rec["total_cost"] <= remaining:
            rec["selected"] = True
            remaining -= rec["total_cost"]
            total_selected_cost += rec["total_cost"]
            total_selected_items += 1

    return RestockingBudgetResponse(
        min_budget=round(min_budget, 2),
        max_budget=round(max_budget, 2),
        current_budget=budget,
        recommendations=recommendations,
        total_selected_cost=round(total_selected_cost, 2),
        total_selected_items=total_selected_items,
    )

@app.post("/api/restocking-orders", response_model=RestockingOrder, status_code=201)
def submit_restocking_order(request: SubmitRestockingOrderRequest):
    """Submit a restocking order from selected recommendations."""
    if not request.items:
        raise HTTPException(status_code=422, detail="Items list cannot be empty")

    now = datetime.now()
    order = {
        "id": str(uuid.uuid4()),
        "order_number": f"RST-{now.strftime('%Y')}-{len(restocking_orders) + 1:04d}",
        "items": [item.model_dump() for item in request.items],
        "total_cost": round(request.total_cost, 2),
        "status": "Submitted",
        "submitted_date": now.isoformat(),
        "expected_delivery": (now + timedelta(days=14)).isoformat(),
    }
    restocking_orders.append(order)
    return order

@app.get("/api/restocking-orders", response_model=List[RestockingOrder])
def get_restocking_orders():
    """Return all submitted restocking orders."""
    return restocking_orders

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
