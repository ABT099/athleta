"""
Helper utilities.
"""
from fastapi import HTTPException, status

from app.clients.api_client import ApiClient, AthleteDTO


def get_athlete_or_404(athlete_id: int) -> AthleteDTO:
    """
    Fetch an athlete from the api service or raise 404. The athlete is api-owned,
    so it is fetched over the wire rather than read from a local table.
    """
    with ApiClient() as api:
        athlete = api.get_athlete(athlete_id)
    if athlete is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Athlete {athlete_id} not found",
        )
    return athlete
