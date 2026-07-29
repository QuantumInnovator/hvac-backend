from fastapi import APIRouter
from fastapi.responses import Response
from twilio.twiml.voice_response import VoiceResponse, Connect


router = APIRouter()


@router.post("/voice")
async def incoming_call():

    response = VoiceResponse()

    connect = Connect()

    connect.stream(
        url="wss://outscore-charred-ridden.ngrok-free.dev/media-stream"
    )

    response.append(connect)

    return Response(
        content=str(response),
        media_type="application/xml"
    )