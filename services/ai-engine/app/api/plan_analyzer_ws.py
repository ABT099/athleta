"""
WebSocket endpoint for real-time plan analysis.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from typing import Dict
import asyncio
import json
from datetime import datetime, timezone

from app.database import get_db
from app.services.plan_analyzer import PlanAnalyzerService
from app.schemas.plan_analyzer import PlanAnalysisResponse


router = APIRouter()


class ConnectionManager:
    """Manages WebSocket connections and debounced analysis."""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.analysis_tasks: Dict[str, asyncio.Task] = {}
        self.debounce_timers: Dict[str, asyncio.Task] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        """Accept WebSocket connection."""
        await websocket.accept()
        self.active_connections[session_id] = websocket
    
    def disconnect(self, session_id: str):
        """Disconnect and cleanup."""
        if session_id in self.active_connections:
            del self.active_connections[session_id]
        
        # Cancel any pending analysis
        if session_id in self.analysis_tasks:
            task = self.analysis_tasks[session_id]
            if not task.done():
                task.cancel()
            del self.analysis_tasks[session_id]
        
        # Cancel debounce timer
        if session_id in self.debounce_timers:
            timer = self.debounce_timers[session_id]
            if not timer.done():
                timer.cancel()
            del self.debounce_timers[session_id]
    
    async def send_message(self, session_id: str, message: Dict):
        """Send message to client."""
        if session_id in self.active_connections:
            websocket = self.active_connections[session_id]
            try:
                await websocket.send_json(message)
            except Exception:
                # Connection closed, cleanup
                self.disconnect(session_id)
    
    async def send_status(self, session_id: str, status: str):
        """Send status update."""
        await self.send_message(session_id, {
            "type": "status",
            "status": status,
            "session_id": session_id,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    async def send_analysis(self, session_id: str, analysis: Dict):
        """Send analysis results."""
        await self.send_message(session_id, {
            "type": "analysis",
            "session_id": session_id,
            "analysis": analysis,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    async def send_error(self, session_id: str, error: str):
        """Send error message."""
        await self.send_message(session_id, {
            "type": "error",
            "session_id": session_id,
            "error": error,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })


manager = ConnectionManager()


@router.websocket("/ws/plan-analyzer/{session_id}")
async def websocket_plan_analyzer(
    websocket: WebSocket,
    session_id: str,
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint for real-time plan analysis.
    
    Client sends plan updates, server responds with analysis.
    Uses 500ms debounce to avoid excessive analysis.
    
    Message format:
    - Client -> Server: {"type": "analyze", "plan_data": {...}, "athlete_id": 123}
    - Server -> Client: {"type": "status", "status": "analyzing"}
    - Server -> Client: {"type": "analysis", "analysis": {...}}
    - Server -> Client: {"type": "error", "error": "..."}
    """
    await manager.connect(websocket, session_id)
    
    try:
        # Send connection confirmation
        await manager.send_status(session_id, "connected")
        
        while True:
            # Receive plan data from client
            data = await websocket.receive_json()
            
            if data.get("type") == "analyze":
                plan_data = data.get("plan_data", {})
                athlete_id = data.get("athlete_id")
                
                # Cancel previous debounce timer if exists
                if session_id in manager.debounce_timers:
                    timer = manager.debounce_timers[session_id]
                    if not timer.done():
                        timer.cancel()
                
                # Cancel previous analysis if still running
                if session_id in manager.analysis_tasks:
                    task = manager.analysis_tasks[session_id]
                    if not task.done():
                        task.cancel()
                
                # Create debounced analysis task
                async def analyze_with_debounce():
                    # Wait for debounce period
                    await asyncio.sleep(0.5)  # 500ms debounce
                    
                    # Send analyzing status
                    await manager.send_status(session_id, "analyzing")
                    
                    try:
                        # Perform analysis
                        analyzer = PlanAnalyzerService(db)
                        result = analyzer.analyze_plan_draft(
                            plan_data=plan_data,
                            athlete_id=athlete_id
                        )
                        
                        # Convert to response format
                        analysis_response = PlanAnalysisResponse(**result)
                        
                        # Send results
                        await manager.send_analysis(
                            session_id,
                            analysis_response.model_dump()
                        )
                    except Exception as e:
                        await manager.send_error(session_id, str(e))
                
                # Start debounced analysis
                analysis_task = asyncio.create_task(analyze_with_debounce())
                manager.analysis_tasks[session_id] = analysis_task
                
            elif data.get("type") == "stop":
                # Cancel analysis
                if session_id in manager.analysis_tasks:
                    task = manager.analysis_tasks[session_id]
                    if not task.done():
                        task.cancel()
                await manager.send_status(session_id, "stopped")
                
    except WebSocketDisconnect:
        manager.disconnect(session_id)
    except Exception as e:
        await manager.send_error(session_id, str(e))
        manager.disconnect(session_id)

