import uvicorn
import json
import datetime

from typing import Any
from fastapi import FastAPI
from fastapi.responses import Response
from fastapi.requests import Request
from mysql import connector as sql

class JSONResponse(Response):
    media_type = "application/json"
    def render(self, content: Any) -> bytes:
        return json.dumps(content, indent=4, separators=(", ", ": ")).encode("utf-8")

app = FastAPI(
    title="iFridge REST",
    version="1.0",
    openapi_url="/api.json",
    redoc_url=None
)

@app.post("/fetch", response_class=JSONResponse)
async def fetch(request: Request) -> JSONResponse:
    db = sql.connect(user="dbuser", password="Foodguardian", host="ifridge.local", database="ifridge")
    cursor = db.cursor()
    cursor.execute("SELECT Item.Productcode, Item.ExpirationDate, Item.Amount, Product.Brand, Product.Name FROM Item JOIN Product ON Item.Productcode = Product.Productcode")
    rows = cursor.fetchall()
    cursor.close()
    db.close()
    return [{"productId": row[0], "brandName": row[3], "productName": row[4], "expirationDate": datetime.datetime.strftime(row[1], "%d/%m/%Y"), "productAmount": row[2]} for row in rows]

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=80)