from __future__ import annotations

from fastapi.testclient import TestClient


AUTH = {"Authorization": "Bearer token-alya"}


def test_health_and_auth_contract(client: TestClient) -> None:
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.post("/api/v1/chat", json={"message": "saldo cuti"}).status_code == 401


def test_chat_returns_contract_and_trace(client: TestClient) -> None:
    response = client.post("/api/v1/chat", headers=AUTH, json={"message": "Berapa jatah cuti tahunan?"})
    assert response.status_code == 200
    payload = response.json()
    assert payload["outcome"] == "answered"
    assert payload["citations"][0]["document_id"] == "HR-LEAVE-001"
    trace = client.get(f"/api/v1/traces/{payload['trace_id']}", headers=AUTH)
    assert trace.status_code == 200
    assert "message" not in trace.json()


def test_monitoring_is_admin_only(client: TestClient) -> None:
    assert client.get("/api/v1/monitoring/summary", headers=AUTH).status_code == 403
    response = client.get(
        "/api/v1/monitoring/summary", headers={"Authorization": "Bearer token-admin"}
    )
    assert response.status_code == 200


def test_trace_cannot_be_read_by_another_employee(client: TestClient) -> None:
    chat = client.post("/api/v1/chat", headers=AUTH, json={"message": "saldo saya"}).json()
    response = client.get(
        f"/api/v1/traces/{chat['trace_id']}",
        headers={"Authorization": "Bearer token-bima"},
    )
    assert response.status_code == 403


def test_dashboard_ui_and_endpoints(client: TestClient) -> None:
    # Dashboard HTML SPA route
    res_ui = client.get("/dashboard")
    assert res_ui.status_code == 200
    assert "text/html" in res_ui.headers["content-type"]
    assert "HR Database & Ops Dashboard" in res_ui.text

    admin_headers = {"Authorization": "Bearer token-admin"}

    # Unauthorized access check
    assert client.get("/api/v1/dashboard/employees").status_code == 401
    assert client.get("/api/v1/dashboard/employees", headers=AUTH).status_code == 403

    # Employees & balances
    res_emp = client.get("/api/v1/dashboard/employees", headers=admin_headers)
    assert res_emp.status_code == 200
    emp_data = res_emp.json()
    assert isinstance(emp_data, list)
    emp_001 = next((e for e in emp_data if e["employee_id"] == "EMP-001"), None)
    assert emp_001 is not None
    assert emp_001["display_name"] == "Alya Pratama"
    annual = next((b for b in emp_001["balances"] if b["leave_type"] == "annual"), None)
    assert annual is not None
    assert annual["available_days"] == 8

    # Leave requests
    res_leave = client.get("/api/v1/dashboard/leave-requests", headers=admin_headers)
    assert res_leave.status_code == 200
    assert isinstance(res_leave.json(), list)

    # Tickets
    res_tickets = client.get("/api/v1/dashboard/tickets", headers=admin_headers)
    assert res_tickets.status_code == 200
    assert isinstance(res_tickets.json(), list)

    # Traces
    res_traces = client.get("/api/v1/dashboard/traces", headers=admin_headers)
    assert res_traces.status_code == 200
    assert isinstance(res_traces.json(), list)


