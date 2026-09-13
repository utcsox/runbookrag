from fastapi import FastAPI

# Make sure the variable name matches "app"
app = FastAPI(title="CI/CD Analyzer API")

@app.get("/")
def health_check():
    return {"status": "healthy"}
