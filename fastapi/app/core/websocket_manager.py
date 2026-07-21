from fastapi import WebSocket
from typing import Dict, List


class ConnectionManager:
    """
    Manages all active WebSocket connections.

    When a user opens the RHH app, their browser connects here.
    When they get a notification, we find their connection and push to it.

    Think of it like a telephone exchange:
    - connect() = someone picks up their phone
    - disconnect() = someone hangs up
    - send_to_user() = calling a specific person's number
    """

    def __init__(self):
        # Dictionary mapping user_id → list of their WebSocket connections
        # A user might have multiple tabs open — that's why it's a list
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, user_id: str, websocket: WebSocket):
        """
        Accepts a new WebSocket connection from a user.
        Called when their browser first connects.
        """
        await websocket.accept()

        # Add this connection to their list
        if user_id not in self.active_connections:
            self.active_connections[user_id] = []
        self.active_connections[user_id].append(websocket)

    def disconnect(self, user_id: str, websocket: WebSocket):
        """
        Removes a WebSocket when user closes the tab or loses connection.
        """
        if user_id in self.active_connections:
            self.active_connections[user_id].remove(websocket)
            # If they have no more open tabs, remove their entry entirely
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]

    async def send_to_user(self, user_id: str, message: dict):
        """
        Sends a notification to a specific user.
        If they have multiple tabs open, all of them receive it.
        If they are offline, we silently skip — the DB already has the notification.
        """
        if user_id not in self.active_connections:
            return  # User is not connected — that's fine, they'll see it next login

        for websocket in self.active_connections[user_id]:
            try:
                await websocket.send_json(message)
            except Exception:
                # Connection dropped mid-send — ignore and continue
                pass

    async def broadcast_to_all(self, message: dict):
        """
        Sends a message to ALL connected users at once.
        Used for admin broadcasts like "platform maintenance in 10 minutes".
        """
        for user_id, connections in self.active_connections.items():
            for websocket in connections:
                try:
                    await websocket.send_json(message)
                except Exception:
                    pass


# One shared instance for the whole app
# Every router imports this same object
manager = ConnectionManager()