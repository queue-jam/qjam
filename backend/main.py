from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"message": "FastAPI is up and running!"}

@app.get("/test/{get_num}")
def read_item(item_id: int, q: str = None):
    return {"get_num": item_id, "q": q}
