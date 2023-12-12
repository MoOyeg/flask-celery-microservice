import uvicorn # pylint: disable=import-error
from app.main import app # pylint: disable=unused-import

if __name__ == "__main__":
    uvicorn.run("run:app", host="0.0.0.0", port=8080, log_level="info")