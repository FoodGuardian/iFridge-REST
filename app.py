import uvicorn
import json
import os
import requests

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

@app.post("/fetch", response_class=JSONResponse)
async def fetch(request: Request) -> JSONResponse:
    db = sql.connect(user="dbuser", password="Foodguardian", host="ifridge.local", database="ifridge")
    cursor = db.cursor()
    cursor.execute("SELECT Item.Productcode, Item.ExpirationDate, Item.Amount, Product.Brand, Product.Name FROM Item JOIN Product ON Item.Productcode = Product.Productcode")
    rows = cursor.fetchall()
    cursor.close()
    db.close()
    return [{"productId": row[0], "brandName": row[3], "productName": row[4], "expiration": {"day": row[1].day, "month": row[1].month, "year": row[1].year}, "productAmount": row[2]} for row in rows]

@app.post("/recipe", response_class=JSONResponse)
async def recipe(request: Request, main_ingredient: str = Form(""), ingredients: List[str] = Form([])) -> JSONResponse:
    global conversation_id
    data = {"access_token": ACCESS_TOKEN, "prompt": f"Maak een recept met {main_ingredient}. Andere beschikbare ingrediënten zijn:\n\n- " + "\n- ".join(ingredients) if len(ingredients) > 0 else "Geen" + "\n\nHoud er rekening mee dat er geen andere ingrediënten in de koelkast staan, dus maak alleen gebruik van de gegeven ingrediënten, niet alle ingrediënten hoeven gebruikt te worden.\n\nReageer alleen met de naam van het recept, een lijst met ingrediënten en instructies, reageer naast dit met niks anders.\n\nLaat geen witregels tussen de verschillende ingrediënten en instructies."}
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

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=80)