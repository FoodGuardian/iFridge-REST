import uvicorn
import json
import os
import requests
import datetime

from typing import Any, List
from fastapi import FastAPI
from fastapi import Form
from fastapi.responses import Response
from fastapi.requests import Request
from mysql import connector as sql
from dotenv import load_dotenv

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
load_dotenv()
conversation_id = None
ACCESS_TOKEN = os.getenv("OPENAI_TOKEN")
DB = sql.connect(user="dbuser", password="Foodguardian", host="ifridge.local", database="ifridge")

@app.post("/fetch", response_class=JSONResponse)
async def fetch(request: Request) -> JSONResponse:
    cursor = DB.cursor()
    cursor.execute("SELECT Item.ID, Item.Productcode, Item.ExpirationDate, Item.Amount, Product.Brand, Product.Name FROM Item JOIN Product ON Item.Productcode = Product.Productcode")
    rows = cursor.fetchall()
    cursor.close()
    return [{"productId": row[0], "productCode": row[1], "brandName": row[4], "productName": row[5], "expiration": {"day": row[2].day, "month": row[2].month, "year": row[2].year}, "productAmount": row[3]} for row in rows]

@app.post("/recipe", response_class=JSONResponse)
async def recipe(request: Request, mainIngredient: str = Form(""), ingredients: List[str] = Form([])) -> JSONResponse:
    global conversation_id
    data = {"access_token": ACCESS_TOKEN, "prompt": f"Maak een recept met {mainIngredient}. Andere beschikbare ingrediënten zijn:\n\n- " + "\n- ".join(ingredients) if len(ingredients) > 0 else "Geen" + "\n\nHoud er rekening mee dat er geen andere ingrediënten in de koelkast staan, dus maak alleen gebruik van de gegeven ingrediënten, niet alle ingrediënten hoeven gebruikt te worden.\n\nReageer alleen met de naam van het recept, een lijst met ingrediënten en instructies, reageer naast dit met niks anders.\n\nLaat geen witregels tussen de verschillende ingrediënten en instructies."}
    if conversation_id:
        data.update({"conversation_id": conversation_id})
    response = requests.post("https://ai.beunhaas.org", data=data)
    if response.status_code == 200:
        conversation_id = response.json()["conversation_id"]
        message = response.json()["message"]
        lines = message.splitlines()
        prefix = lines[0]
        ingredients = []
        instructions = []
        suffix = lines[-1] if len(lines[-1]) > 0 and not lines[-1][0].isdigit() else ""
        for line in lines:
            if line.startswith("- "):
                ingredients.append(line.split("- ", 1)[-1])
            elif len(line) > 0 and line[0].isdigit():
                instructions.append(line.split(". ", 1)[-1])
        return {"prefix": prefix, "ingredients": ingredients, "instructions": instructions, "suffix": suffix}
    else:
        return JSONResponse({"msg": "Something went wrong."}, 500)

@app.post("/delete", response_class=JSONResponse)
async def delete(request: Request, productId: int = Form(0)) -> JSONResponse:
    cursor = DB.cursor()
    cursor.execute("SELECT Amount FROM Item WHERE ID = %s", (productId,))
    row = cursor.fetchone()
    cursor.close()
    if not row or len(row) == 0:
        return JSONResponse({"msg": "Product not found."}, 404)
    elif row[0] > 1:
        cursor.execute("UPDATE Item SET Amount = %s WHERE ID = %s", (row[0] - 1, productId))
    else:
        cursor.execute("DELETE FROM Item WHERE ID = %s", productId)
    return {"msg": "Product deleted."}

@app.post("/edit", response_class=JSONResponse)
async def edit(request: Request, productId: int = Form(0), day: int = Form(0), month: int = Form(0), year: int = Form(0)) -> JSONResponse:
    cursor = DB.cursor()
    cursor.execute("SELECT ID FROM Item WHERE ID = %s", (productId,))
    row = cursor.fetchone()
    cursor.close()
    if not row or len(row) == 0:
        return JSONResponse({"msg": "Product not found."}, 404)
    else:
        try:
            date = datetime.date(year, month, day)
            if date < datetime.date.today():
                return JSONResponse({"msg": "Date cannot be in the past."}, 400)
            else:
                cursor.execute("UPDATE Item SET ExpirationDate = %s WHERE ID = %s", (date, productId))
                return {"msg": "Product updated."}
        except:
            return JSONResponse({"msg": "Malformed date."}, 400)

if __name__ == "__main__":
    try:
        uvicorn.run("app:app", host="0.0.0.0", port=80)
    except:
        DB.close()
