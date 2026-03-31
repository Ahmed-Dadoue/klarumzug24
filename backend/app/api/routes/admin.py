import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, StreamingResponse

from app.api import require_admin_api_key, success_response
from app.core.database import SessionLocal
from app.core.serialization import serialize_lead
from app.models import CompanyDB, LeadDB, TransactionDB

router = APIRouter()

LEAD_EXPORT_FIELDNAMES = [
    "id",
    "name",
    "phone",
    "email",
    "from_city",
    "to_city",
    "rooms",
    "distance_km",
    "express",
    "company_id",
    "status",
    "assigned_price_eur",
    "accepted_agb",
    "accepted_privacy",
    "created_at",
]


@router.get("/api/admin/invoices/summary")
def invoices_summary(_admin: None = Depends(require_admin_api_key)):
    db = SessionLocal()
    try:
        companies = db.query(CompanyDB).order_by(CompanyDB.id.asc()).all()
        result = []
        for company in companies:
            txns = (
                db.query(TransactionDB)
                .filter(
                    TransactionDB.company_id == company.id,
                    TransactionDB.status == "charged",
                )
                .all()
            )
            charged_total = int(sum(t.amount_eur for t in txns))
            result.append(
                {
                    "company_id": company.id,
                    "company_name": company.name,
                    "charged_count": len(txns),
                    "charged_total_eur": charged_total,
                    "balance_eur": float(company.balance_eur or 0),
                }
            )
        return success_response(
            "Invoice summary loaded",
            data={"invoices": result},
            legacy={"invoices": result},
        )
    finally:
        db.close()


@router.get("/api/admin/leads/export")
def export_leads_csv(
    status: str | None = Query(default=None),
    company_id: int | None = Query(default=None),
    _admin: None = Depends(require_admin_api_key),
):
    db = SessionLocal()
    try:
        query = db.query(LeadDB)
        if status:
            query = query.filter(LeadDB.status == status)
        if company_id is not None:
            query = query.filter(LeadDB.company_id == company_id)

        rows = query.order_by(LeadDB.id.desc()).all()

        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=LEAD_EXPORT_FIELDNAMES,
        )
        writer.writeheader()
        for row in rows:
            serialized = serialize_lead(row, include_pii=True)
            writer.writerow({field: serialized.get(field) for field in LEAD_EXPORT_FIELDNAMES})

        csv_bytes = output.getvalue().encode("utf-8")
        filename = f"klarumzug24-leads-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.csv"
        return StreamingResponse(
            io.BytesIO(csv_bytes),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    finally:
        db.close()


@router.get("/admin", response_class=HTMLResponse)
def admin_dashboard_page():
    return """
<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Klarumzug24 Admin</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 24px; }
    .row { display: flex; gap: 8px; margin-bottom: 12px; flex-wrap: wrap; }
    input, select, button { padding: 8px; }
    table { border-collapse: collapse; width: 100%; margin-top: 12px; }
    th, td { border: 1px solid #ddd; padding: 8px; font-size: 14px; }
    th { background: #f5f5f5; }
    .small { font-size: 12px; color: #555; }
  </style>
</head>
<body>
  <h1>Klarumzug24 Admin</h1>
  <div class=\"row\">
    <input id=\"apiKey\" placeholder=\"Admin API key\" style=\"min-width:320px\" />
    <button onclick=\"loadData()\">Load</button>
    <button onclick=\"downloadCsv()\">Export CSV</button>
  </div>
  <div class=\"row\">
    <select id=\"status\">
      <option value=\"\">all status</option>
      <option value=\"new\">new</option>
      <option value=\"assigned\">assigned</option>
      <option value=\"accepted\">accepted</option>
      <option value=\"rejected\">rejected</option>
    </select>
    <input id=\"companyId\" type=\"number\" placeholder=\"company id\" />
  </div>
  <div class=\"small\" id=\"summary\">-</div>
  <table>
    <thead>
      <tr>
        <th>ID</th><th>Status</th><th>Company</th><th>Price</th><th>Name</th><th>Phone</th><th>Email</th><th>Created</th>
      </tr>
    </thead>
    <tbody id=\"rows\"></tbody>
  </table>

<script>
async function api(url) {
  const key = document.getElementById('apiKey').value.trim();
  const res = await fetch(url, { headers: { 'X-API-Key': key } });
  let payload = null;
  try {
    payload = await res.json();
  } catch (_) {
    payload = null;
  }
  if (!res.ok) {
    throw new Error(payload?.message || ('HTTP ' + res.status));
  }
  if (payload && payload.ok === false) {
    throw new Error(payload.message || 'API error');
  }
  return payload;
}

function buildQuery() {
  const status = document.getElementById('status').value;
  const companyId = document.getElementById('companyId').value;
  const params = new URLSearchParams();
  if (status) params.set('status', status);
  if (companyId) params.set('company_id', companyId);
  const q = params.toString();
  return q ? ('?' + q) : '';
}

async function loadData() {
  try {
    const q = buildQuery();
    const leadsPayload = await api('/api/leads' + q);
    const invoicesPayload = await api('/api/admin/invoices/summary');
    const leads = Array.isArray(leadsPayload)
      ? leadsPayload
      : (leadsPayload?.data?.leads ?? leadsPayload?.leads ?? []);
    const invoices = Array.isArray(invoicesPayload)
      ? invoicesPayload
      : (invoicesPayload?.data?.invoices ?? invoicesPayload?.invoices ?? []);

    document.getElementById('summary').textContent =
      'Leads: ' + leads.length + ' | Companies: ' + invoices.length;

    const rows = document.getElementById('rows');
    rows.innerHTML = leads.map(l => `
      <tr>
        <td>${l.id}</td>
        <td>${l.status ?? ''}</td>
        <td>${l.company_id ?? ''}</td>
        <td>${l.assigned_price_eur ?? ''}</td>
        <td>${l.name ?? ''}</td>
        <td>${l.phone ?? ''}</td>
        <td>${l.email ?? ''}</td>
        <td>${l.created_at ?? ''}</td>
      </tr>
    `).join('');
  } catch (e) {
    alert('Load failed: ' + e.message);
  }
}

async function downloadCsv() {
  try {
    const key = document.getElementById('apiKey').value.trim();
    const q = buildQuery();
    const res = await fetch('/api/admin/leads/export' + q, {
      headers: { 'X-API-Key': key }
    });
    if (!res.ok) throw new Error('HTTP ' + res.status);

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'leads.csv';
    a.click();
    URL.revokeObjectURL(url);
  } catch (e) {
    alert('CSV export failed: ' + e.message);
  }
}
</script>
</body>
</html>
"""
