from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from app.stookwijzer.stookwijzerapi import Stookwijzer
import aiohttp
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = FastAPI(title="Stookwijzer API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def root():
    return {"message": "Welcome to Stookwijzer API"}

@app.get("/api/stookwijzer")
async def get_stookwijzer_data(latitude: float, longitude: float):
    try:
        logger.debug(f"Received request for coordinates: lat={latitude}, lon={longitude}")
        
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            logger.debug("Attempting coordinate transformation...")
            x, y = await Stookwijzer.async_transform_coordinates(session, latitude, longitude)
            
            if x is None or y is None:
                logger.error("Failed to transform coordinates")
                raise HTTPException(
                    status_code=400, 
                    detail="Failed to transform coordinates"
                )
            
            logger.debug(f"Coordinates transformed successfully: x={x}, y={y}")
            sw = Stookwijzer(session, x, y)
            
            logger.debug("Fetching Stookwijzer data...")
            await sw.async_update()
            
            if sw.advice is None:
                logger.error("No data available for these coordinates")
                raise HTTPException(
                    status_code=404, 
                    detail="No data available for these coordinates"
                )
            
            response_data = {
                "advice": sw.advice,
                "alert": sw.alert,
                "windspeed_bft": sw.windspeed_bft,
                "windspeed_ms": sw.windspeed_ms,
                "lki": sw.lki,
                "forecast_advice": sw.forecast_advice,
                "forecast_alert": sw.forecast_alert,
                "last_updated": sw.last_updated.isoformat() if sw.last_updated else None,
                "coordinates": {
                    "original": {"latitude": latitude, "longitude": longitude},
                    "transformed": {"x": x, "y": y}
                }
            }
            
            logger.debug(f"Successfully prepared response: {response_data}")
            return response_data
            
    except Exception as e:
        logger.exception("Error in get_stookwijzer_data")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/healthcheck")
async def healthcheck():
    """Basic health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}
