"""
Tests for restocking API endpoints.
"""
import pytest


class TestRestockingRecommendations:
    """Test suite for GET /api/restocking/recommendations."""

    def test_get_recommendations_default_budget(self, client):
        """Test getting recommendations with default budget."""
        response = client.get("/api/restocking/recommendations")
        assert response.status_code == 200

        data = response.json()
        assert "min_budget" in data
        assert "max_budget" in data
        assert "current_budget" in data
        assert "recommendations" in data
        assert "total_selected_cost" in data
        assert "total_selected_items" in data
        assert isinstance(data["recommendations"], list)
        assert len(data["recommendations"]) > 0

    def test_recommendations_sorted_by_priority(self, client):
        """Test that recommendations are sorted by priority_score descending."""
        response = client.get("/api/restocking/recommendations?budget=999999")
        data = response.json()

        scores = [r["priority_score"] for r in data["recommendations"]]
        assert scores == sorted(scores, reverse=True)

    def test_recommendation_structure(self, client):
        """Test that each recommendation has the correct fields."""
        response = client.get("/api/restocking/recommendations")
        data = response.json()

        for rec in data["recommendations"]:
            assert "sku" in rec
            assert "name" in rec
            assert "unit_cost" in rec
            assert "quantity_on_hand" in rec
            assert "forecasted_demand" in rec
            assert "demand_gap" in rec
            assert "restock_quantity" in rec
            assert "total_cost" in rec
            assert "priority_score" in rec
            assert "selected" in rec
            assert isinstance(rec["unit_cost"], (int, float))
            assert isinstance(rec["demand_gap"], int)
            assert rec["demand_gap"] > 0
            assert rec["restock_quantity"] == rec["demand_gap"]

    def test_budget_constrains_selection(self, client):
        """Test that budget parameter constrains which items are selected."""
        # Very small budget — should select fewer items
        response = client.get("/api/restocking/recommendations?budget=100")
        data = response.json()

        selected = [r for r in data["recommendations"] if r["selected"]]
        assert data["total_selected_cost"] <= 100
        assert data["total_selected_items"] == len(selected)

    def test_large_budget_selects_all(self, client):
        """Test that a very large budget selects all items."""
        response = client.get("/api/restocking/recommendations?budget=9999999")
        data = response.json()

        selected = [r for r in data["recommendations"] if r["selected"]]
        assert len(selected) == len(data["recommendations"])
        assert abs(data["total_selected_cost"] - data["max_budget"]) < 0.01

    def test_min_max_budget_values(self, client):
        """Test that min_budget and max_budget are computed correctly."""
        response = client.get("/api/restocking/recommendations?budget=9999999")
        data = response.json()

        costs = [r["total_cost"] for r in data["recommendations"]]
        assert abs(data["min_budget"] - min(costs)) < 0.01
        assert abs(data["max_budget"] - sum(costs)) < 0.01

    def test_total_cost_equals_quantity_times_unit_cost(self, client):
        """Test that total_cost = restock_quantity * unit_cost for each item."""
        response = client.get("/api/restocking/recommendations")
        data = response.json()

        for rec in data["recommendations"]:
            expected = rec["restock_quantity"] * rec["unit_cost"]
            assert abs(rec["total_cost"] - round(expected, 2)) < 0.01


class TestSubmitRestockingOrder:
    """Test suite for POST /api/restocking-orders."""

    def test_submit_order_success(self, client):
        """Test submitting a restocking order returns 201."""
        payload = {
            "items": [
                {"sku": "WDG-001", "name": "Industrial Widget Type A", "quantity": 100, "unit_cost": 24.99}
            ],
            "total_cost": 2499.00
        }
        response = client.post("/api/restocking-orders", json=payload)
        assert response.status_code == 201

        data = response.json()
        assert "id" in data
        assert "order_number" in data
        assert data["order_number"].startswith("RST-")
        assert data["status"] == "Submitted"
        assert "submitted_date" in data
        assert "expected_delivery" in data
        assert len(data["items"]) == 1

    def test_submit_order_empty_items_returns_422(self, client):
        """Test that submitting with empty items list returns 422."""
        payload = {
            "items": [],
            "total_cost": 0
        }
        response = client.post("/api/restocking-orders", json=payload)
        assert response.status_code == 422

    def test_submit_order_missing_fields_returns_422(self, client):
        """Test that missing required fields returns 422."""
        response = client.post("/api/restocking-orders", json={})
        assert response.status_code == 422


class TestGetRestockingOrders:
    """Test suite for GET /api/restocking-orders."""

    def test_get_orders_returns_list(self, client):
        """Test that GET returns a list."""
        response = client.get("/api/restocking-orders")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    def test_submitted_order_appears_in_list(self, client):
        """Test that a submitted order appears when fetching all orders."""
        # Submit an order
        payload = {
            "items": [
                {"sku": "BRG-102", "name": "Steel Bearing Assembly", "quantity": 50, "unit_cost": 89.50}
            ],
            "total_cost": 4475.00
        }
        post_response = client.post("/api/restocking-orders", json=payload)
        assert post_response.status_code == 201
        created = post_response.json()

        # Fetch all and check it's there
        get_response = client.get("/api/restocking-orders")
        assert get_response.status_code == 200

        orders = get_response.json()
        order_ids = [o["id"] for o in orders]
        assert created["id"] in order_ids
