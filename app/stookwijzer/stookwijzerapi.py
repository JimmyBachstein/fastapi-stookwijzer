"""The Stookwijze API."""
from datetime import datetime, timedelta
import aiohttp
import asyncio
import json
import logging
import pytz

_LOGGER = logging.getLogger(__name__)

class Stookwijzer(object):
    """The Stookwijze API."""

    def __init__(self, session: aiohttp.ClientSession, x: float, y: float):
        self._boundary_box = self.get_boundary_box(x, y)
        self._advice = None
        self._alert = None
        self._last_updated = None
        self._stookwijzer = None
        self._session = session

    @property
    def advice(self) -> str | None:
        """Return the advice."""
        return self._advice

    @property
    def alert(self) -> bool | None:
        """Return the stookalert."""
        return self._alert

    @property
    def windspeed_bft(self) -> int | None:
        """Return the windspeed in bft."""
        return self.get_property("wind_bft")

    @property
    def windspeed_ms(self) -> float | None:
        """Return the windspeed in m/s."""
        windspeed = self.get_property("wind")
        return round(float(windspeed), 1) if windspeed else windspeed

    @property
    def lki(self) -> int | None:
        """Return the lki."""
        return self.get_property("lki")

    @property
    def forecast_advice(self) -> list:
        """Return the forecast array for advices."""
        return self.get_forecast_array(True)

    @property
    def forecast_alert(self) -> list:
        """Return the forecast array for alerts."""
        return self.get_forecast_array(False)

    @property
    def last_updated(self) -> datetime | None:
        """Get the last updated date."""
        return self._last_updated

    @staticmethod
    async def async_transform_coordinates(session: aiohttp.ClientSession, latitude: float, longitude: float):
        """Transform the coordinates from EPSG:4326 to EPSG:28992."""
        try:
            url = f"https://epsg.io/trans?x={longitude}&y={latitude}&s_srs=4326&t_srs=28992"
            async with session.get(url=url, timeout=10) as response:
                text = await response.text()
                coordinates = json.loads(text)
                return float(coordinates["x"]), float(coordinates["y"])
        except Exception as e:
            _LOGGER.error(f"Error in coordinate transformation: {str(e)}")
            return None, None

    async def async_update(self) -> None:
        """Get the stookwijzer data."""
        self._stookwijzer = await self.async_get_stookwijzer()

        advice = self.get_property("advies_0")
        if advice:
            self._advice = self.get_color(advice)
            self._alert = self.get_property("alert_0") == "1"
            self._last_updated = datetime.now()

    def get_forecast_array(self, advice: bool) -> list:
        """Return the forecast array."""
        forecast = []
        runtime = self.get_property("model_runtime")

        if not runtime:
            return None

        dt = datetime.strptime(runtime, "%d-%m-%Y %H:%M")
        localdt = dt.astimezone(pytz.timezone("Europe/Amsterdam"))

        for offset in range(2, 25, 2):
            forecast.append(self.get_forecast_at_offset(localdt, offset, advice))

        return forecast

    def get_forecast_at_offset(self, runtime: datetime, offset: int, advice: bool) -> dict:
        """Get forecast at a certain offset."""
        dt = {"datetime": (runtime + timedelta(hours=offset)).isoformat()}
        forecast = (
            {"advice": self.get_color(self.get_property("advies_" + str(offset)))}
            if advice
            else {"alert": self.get_property("alert_" + str(offset)) == "1"}
        )
        dt.update(forecast)
        return dt

    def get_boundary_box(self, x: float, y: float) -> str | None:
        """Create a boundary box with the coordinates"""
        try:
            # Format coordinates with fixed precision
            return "{:.6f}%2C{:.6f}%2C{:.6f}%2C{:.6f}".format(
                float(x),
                float(y),
                float(x) + 10.0,
                float(y) + 10.0
            )
        except (ValueError, TypeError) as e:
            _LOGGER.error(f"Invalid coordinates for boundary box: {str(e)}")
            return None

    def get_color(self, advice: str) -> str:
        """Convert the Stookwijzer data into a color."""
        if advice == "0":
            return "code_yellow"
        if advice == "1":
            return "code_orange"
        if advice == "2":
            return "code_red"
        return ""

    def get_property(self, prop: str) -> str:
        """Get a feature from the JSON data"""
        try:
            return str(self._stookwijzer["features"][0]["properties"][prop])
        except (KeyError, IndexError, TypeError):
            _LOGGER.error(f"Property {prop} not available")
            return ""

    async def async_get_stookwijzer(self):
        """Get the stookwijzer data."""
        if not self._boundary_box:
            _LOGGER.error("No boundary box available")
            return None

        url = (
            f"https://data.rivm.nl/geo/alo/wms"
            f"?service=WMS"
            f"&VERSION=1.3.0"
            f"&REQUEST=GetFeatureInfo"
            f"&FORMAT=application%2Fjson"
            f"&QUERY_LAYERS=stookwijzer"
            f"&LAYERS=stookwijzer"
            f"&servicekey=82b124ad-834d-4c10-8bd0-ee730d5c1cc8"
            f"&STYLES="
            f"&BUFFER=1"
            f"&info_format=application%2Fjson"
            f"&feature_count=1"
            f"&I=1&J=1"
            f"&WIDTH=1&HEIGHT=1"
            f"&CRS=EPSG%3A28992"
            f"&BBOX={self._boundary_box}"
        )

        try:
            async with self._session.get(url=url, allow_redirects=False, timeout=10) as response:
                text = await response.text()
                return json.loads(text)
        except Exception as e:
            _LOGGER.error(f"Error getting Stookwijzer data: {str(e)}")
            return None
