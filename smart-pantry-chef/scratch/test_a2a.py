import asyncio
import os
import uuid
import google.auth
import google.auth.transport.requests
import httpx
from a2a.client import ClientConfig, ClientFactory
from a2a.types import (
    AgentCard,
    Message,
    Part,
    Role,
    TextPart,
    TransportProtocol,
)

RESOURCE = "projects/261479101784/locations/us-east1/reasoningEngines/204696079743057920"
AGENT_DIRECTORY = "app"
LOCATION = "us-east1"

A2A_BASE = (
    f"https://{LOCATION}-aiplatform.googleapis.com/reasoningEngines/v1/"
    f"{RESOURCE}/api/a2a/{AGENT_DIRECTORY}"
)
A2A_CARD_URL = f"{A2A_BASE}/.well-known/agent-card.json"

_creds, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])

def _auth_headers():
    _creds.refresh(google.auth.transport.requests.Request())
    return {
        "Authorization": f"Bearer {_creds.token}",
        "Content-Type": "application/json",
    }

async def main():
    async with httpx.AsyncClient(headers=_auth_headers(), timeout=120) as client:
        resp = await client.get(A2A_CARD_URL)
        card = AgentCard(**resp.json())
        card.url = A2A_BASE
        
        factory = ClientFactory(
            ClientConfig(
                supported_transports=[
                    TransportProtocol.jsonrpc,
                    TransportProtocol.http_json,
                ],
                httpx_client=client,
            )
        )
        a2a_client = factory.create(card)
        
        msg = Message(
            message_id=str(uuid.uuid4()),
            role=Role.user,
            parts=[Part(root=TextPart(text="Hello"))],
        )
        
        print("Sending message...")
        async for event in a2a_client.send_message(msg):
            print("EVENT:", type(event), repr(event))

if __name__ == "__main__":
    asyncio.run(main())
